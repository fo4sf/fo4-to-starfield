"""Synthetic tests for the Commonwealth overlay grid: src/fo4sf/overlay_grid.py (tiles, frames, seams, masks, planet
placement hypothesis) and scripts/terrain/make_cw_overlays.py (build from made-up FO4 heights, offline check).
No game data: every height here is a formula."""
import argparse
import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
from fo4sf import btd, overlay  # noqa: E402
from fo4sf import overlay_grid as og  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402
import make_cw_overlays as mco  # noqa: E402


class Region(unittest.TestCase):
    def test_fo4_rect_to_sf_cells(self):
        # experiment 3: FO4 cells x -35..10, y -6..40 -> Starfield cells x -21..6, y -4..23 (28 x 28)
        self.assertEqual(og.sf_cells_of_fo4_rect(-35, 10, -6, 40), (-21, 6, -4, 23))
        # the whole LAND grid, 192 FO4 cells = 11,234.7 m -> 114 Starfield cells
        x0, x1, y0, y1 = og.sf_cells_of_fo4_rect(-96, 95, -96, 95)
        self.assertEqual((x0, x1), (-57, 56))
        self.assertEqual(x1 - x0 + 1, 114)

    def test_split_two_by_two(self):
        tiles = og.split(-21, 6, -4, 23, 14)
        self.assertEqual(len(tiles), 4)
        self.assertEqual([(t.ix, t.iy, t.cx0, t.cy0) for t in tiles],
                         [(0, 0, -21, -4), (1, 0, -7, -4), (0, 1, -21, 10), (1, 1, -7, 10)])
        self.assertEqual(og.grid_shape(tiles), (2, 2))
        self.assertEqual(tiles[0].tag, "00")
        self.assertEqual(tiles[3].cells_x, (-7, 6))

    def test_padding(self):
        # 114 cells in tiles of 14 -> 9 tiles = 126 cells; 'centre' puts 6 extra cells on each side
        tiles = og.split(-57, 56, -57, 56, 14)
        xs = sorted({t.cx0 for t in tiles})
        self.assertEqual(len(xs), 9)
        self.assertEqual(xs[0], -63)
        self.assertEqual(xs[-1] + 14 - 1, 62)
        sw = og.split(-57, 56, -57, 56, 14, pad="sw")
        self.assertEqual(min(t.cx0 for t in sw), -57)
        one = og.split(-21, 6, -4, 23, 28)            # one tile = option (a), one overlay
        self.assertEqual(len(one), 1)
        self.assertEqual(og.outer_edges(one[0], one), ("w", "e", "s", "n"))
        with self.assertRaises(ValueError):
            og.split(0, 9, 0, 9, 2)

    def test_origin_padding(self):
        # the playable core (Starfield cells x -20..18, y -23..18) as one 64-cell overlay whose frame is the CW frame
        one = og.split(-20, 18, -23, 18, 64, pad="origin")
        self.assertEqual(len(one), 1)
        self.assertEqual((one[0].cells_x, one[0].cells_y), ((-32, 31), (-32, 31)))
        self.assertEqual(one[0].origin_m, (0.0, 0.0))
        self.assertEqual(one[0].to_local(-989.0286, 1147.2), (-989.0286, 1147.2))
        # a grid: tile origins on multiples of 14 cells, one tile centred on the CW origin
        tiles = og.split(-21, 6, -4, 23, 14, pad="origin")
        self.assertTrue(all((t.cx0 + 7) % 14 == 0 and (t.cy0 + 7) % 14 == 0 for t in tiles))
        self.assertIn((0.0, 0.0), [t.origin_m for t in tiles])
        self.assertTrue(min(t.cx0 for t in tiles) <= -21 and max(t.cx0 + 13 for t in tiles) >= 6)
        with self.assertRaises(ValueError):
            og.split(0, 9, 0, 9, 5, pad="middle")

    def test_frames_round_trip(self):
        t = og.Tile(1, 0, -7, -4, 14)
        self.assertEqual(t.origin_m, (0.0, 300.0))          # cell -7 + 14 // 2 = 0, cell -4 + 7 = 3
        self.assertEqual(t.to_local(-989.0286, 1147.2), (-989.0286, 847.2))
        self.assertEqual(t.to_cw(*t.to_local(12.5, -40.0)), (12.5, -40.0))
        x0, x1, y0, y1 = t.bounds_m
        self.assertEqual((x0, x1, y0, y1), (-700.0, 700.0, -400.0, 1000.0))
        lx0, lx1, _, _ = (v - o for v, o in zip(t.bounds_m, (0.0, 0.0, 300.0, 300.0)))
        self.assertEqual(lx0, tg.grid_origin(14))             # the BTD's SW sample in the tile's own frame
        self.assertTrue(t.contains(-700.0, -400.0) and not t.contains(700.0, 0.0))

    def test_adjacent_lattices_continue(self):
        a, b = og.Tile(0, 0, -21, -4, 14), og.Tile(1, 0, -7, -4, 14)
        xa, _ = a.sample_coords()
        xb, _ = b.sample_coords()
        self.assertEqual(len(xa), 14 * 128)
        self.assertEqual(xb[0] - xa[-1], tg.SF_STEP_M)       # one step across the seam, as inside one BTD
        self.assertEqual(xb[0], a.bounds_m[1])

    def test_seams_and_edges(self):
        tiles = og.split(-21, 6, -4, 23, 14)
        s = og.seams(tiles)
        self.assertEqual(len(s), 4)
        self.assertEqual(sorted((x["axis"], x["at_m"]) for x in s),
                         [("x", -700.0), ("x", -700.0), ("y", 1000.0), ("y", 1000.0)])
        self.assertEqual({x["name"] for x in s}, {"T00|T10", "T00/T01", "T10/T11", "T01|T11"})
        self.assertEqual(og.outer_edges(tiles[0], tiles), ("w", "s"))
        self.assertEqual(og.outer_edges(tiles[3], tiles), ("e", "n"))
        self.assertIs(og.tile_at(tiles, -989.0, 1147.0), tiles[2])
        self.assertIsNone(og.tile_at(tiles, 700.0, 0.0))

    def test_height_range(self):
        self.assertEqual(og.height_range(-114.46, 140.67), (-116.0, 142.0))   # experiment 2's range


class Masks(unittest.TestCase):
    def test_ring_only_on_outer_edges(self):
        a = overlay.mask_array(5, edges=("w", "s"))
        self.assertTrue((a[:, :100] == 255).all())               # west column of cells
        self.assertTrue((a[400:, :] == 255).all())               # south row (rows are north-first)
        self.assertTrue((a[:400, 100:] == 0).all())              # seams east and north stay 0
        self.assertEqual(overlay.mask_check(a, 5, edges=("w", "s")), (0, 0))
        self.assertNotEqual(overlay.mask_check(a, 5)[0], 0)      # differs from the full ring
        full = overlay.mask_array(5)
        self.assertTrue((full == overlay.mask_array(5, edges=("w", "e", "s", "n"))).all())
        dds = overlay.dds_bc4(a)
        self.assertTrue((overlay.bc4_decode(dds) == a).all())
        with self.assertRaises(ValueError):
            overlay.mask_array(5, edges=("x",))


class Planet(unittest.TestCase):
    def test_reference_maps_to_its_measured_offset(self):
        self.assertEqual(og.predicted_offset(*og.WORLD01_LATLON), (30.0, -35.0))

    def test_round_trip_and_scale(self):
        for target in ((-7, -7), (7, 7), (0, 0), (-40, 25)):
            lat, lon = og.latlon_for_offset(target)
            x, y = og.predicted_offset(lat, lon)
            self.assertAlmostEqual(x, target[0], places=6)
            self.assertAlmostEqual(y, target[1], places=6)
        k = og.cells_per_radian(og.MARS_RADIUS_KM)
        self.assertEqual(k, 33900.0)                              # 3,390 km / 100 m per radian
        lat0, lon0 = og.latlon_for_offset((30, -34))              # one cell north of the reference
        self.assertAlmostEqual(lat0 - 0.2, 1 / k, places=12)
        self.assertAlmostEqual(lon0, 1.2, places=12)
        lat1, lon1 = og.latlon_for_offset((31, -35))              # one cell east: 1 / (k cos lat)
        self.assertAlmostEqual(lon1 - 1.2, 1 / (k * math.cos(0.2)), places=12)

    def test_group_targets_are_edge_to_edge(self):
        tiles = og.split(-21, 6, -4, 23, 14)
        t = og.group_targets(tiles)
        self.assertEqual([t[x] for x in tiles], [(-7, -7), (7, -7), (-7, 7), (7, 7)])
        self.assertTrue(og.check_adjacent(tiles, t))
        moved = dict(t)
        moved[tiles[1]] = (8, -7)
        self.assertFalse(og.check_adjacent(tiles, moved))
        nine = og.split(0, 41, 0, 41, 14)
        self.assertTrue(og.check_adjacent(nine, og.group_targets(nine, (3, -2))))


# --------------------------------------------------------------------------------------------- synthetic build
def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rbytes(path):
    with open(path, "rb") as f:
        return f.read()


def synthetic_npz(path, lo=-12, hi=11):
    """FO4 LAND grids for cells lo..hi on both axes from one smooth formula (FO4 units), so shared edges match."""
    grid, heights = [], []
    k = np.arange(33) * 128.0
    for cy in range(lo, hi + 1):
        for cx in range(lo, hi + 1):
            xu = cx * 4096.0 + k[None, :]
            yu = cy * 4096.0 + k[:, None]
            z = 3000.0 * np.sin(xu / 20000.0) + 2000.0 * np.cos(yu / 15000.0) + 0.02 * xu
            grid.append((cx, cy))
            heights.append(z)
    np.savez(path, grid=np.array(grid, np.int32), heights=np.array(heights, np.float32))


def build_args(out, npz, **kw):
    a = dict(cmd="build", fo4=None, fo4_npz=npz, sf_data="unused", out=out, fo4_cells=[-8, 7, -8, 7], tile=5,
             pad="centre", prefix="FO4CWT", plugin="FO4TerrainTest.esm", mars_plugin="FO4TerrainTest_Mars.esm",
             no_mars=False, experiment="terrain_test", alignment="absolute", hnam=0, radius_km=og.MARS_RADIUS_KM,
             ref_lat=0.2, ref_lon=1.2, ref_offset=[30, -35], centre_cell=[0, 0], mask_writer="builtin", grid_points=0)
    a.update(kw)
    return argparse.Namespace(**a)


class SyntheticBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.npz = os.path.join(cls.tmp.name, "fo4.npz")
        synthetic_npz(cls.npz)
        cls.out = os.path.join(cls.tmp.name, "stage")
        os.makedirs(cls.out)
        cls._ltex = mco.ltex_source
        mco.ltex_source = lambda sf_data: ([0x001235C2], bytes([1, 0, 0, 0, 0, 0, 0, 0]))
        with contextlib.redirect_stdout(io.StringIO()):
            mco.build(build_args(cls.out, cls.npz))
        cls.prm = jload(os.path.join(cls.out, "overlays_params.json"))
        cls.plan = jload(os.path.join(cls.out, "plan.json"))

    @classmethod
    def tearDownClass(cls):
        mco.ltex_source = cls._ltex
        cls.tmp.cleanup()

    def test_layout(self):
        ovs = self.prm["overlays"]
        self.assertEqual([o["world"] for o in ovs], ["FO4CWT_T00", "FO4CWT_T10", "FO4CWT_T01", "FO4CWT_T11"])
        self.assertEqual([o["anchor"]["form_id"] for o in ovs], [0x800, 0x801, 0x802, 0x803])
        self.assertEqual([o["anchor"]["ref"] for o in ovs], ["02000800", "02000801", "02000802", "02000803"])
        self.assertEqual(ovs[0]["cells_cw"], {"x": [-5, -1], "y": [-5, -1]})
        self.assertEqual([o["planet_target_cell"] for o in ovs], [[-3, -3], [2, -3], [-3, 2], [2, 2]])
        self.assertEqual([o["mask_outer_edges"] for o in ovs], [["w", "s"], ["e", "s"], ["w", "n"], ["e", "n"]])
        self.assertEqual(len({o["location"] for o in ovs}), 4)
        for o in ovs:
            self.assertEqual(len(o["fnam"]), 25)
            self.assertEqual(o["spawn"][2], round(o["anchor"]["local"][2] + 2.0, 4))

    def test_tiles_equal_one_big_btd(self):
        """Edge matching: the four tiles' raw samples, side by side, are exactly the samples of one 10 x 10-cell BTD
        of the same region with the same height range."""
        fo4 = mco.Fo4Heights(npz=self.npz)
        big = og.Tile(0, 0, -5, -5, 10)
        want = btd.quantize(mco.tile_heights(fo4, big), self.prm["hmin"], self.prm["hmax"])
        got = np.zeros_like(want)
        for o in self.prm["overlays"]:
            t = btd.read(rbytes(os.path.join(self.out, *o["btd_file"].split("/"))))
            r0 = (o["cells_cw"]["y"][0] + 5) * 128
            c0 = (o["cells_cw"]["x"][0] + 5) * 128
            got[r0:r0 + 640, c0:c0 + 640] = t.heights_raw
            self.assertEqual((t.hmin, t.hmax), (self.prm["hmin"], self.prm["hmax"]))
        self.assertTrue((got == want).all())

    def test_plan_entries(self):
        self.assertEqual(len(self.plan), 4 + 1 + 3)
        kinds = [e["label"].split(":")[0] for e in self.plan]
        self.assertEqual(kinds[4], "terrain_test group")
        group = self.plan[4]
        self.assertEqual(len(group["points"]), 4 * 3 * 2)        # 4 seam segments x 3 distances x 2 sides
        for e in self.plan[5:]:
            self.assertNotIn("spawn_local", e)                   # read from the first tile's landing: no fallback
            self.assertEqual(e["coc"], self.plan[0]["coc"])
        tiles = {o["anchor"]["ref"]: og.Tile(o["ix"], o["iy"], o["cells_cw"]["x"][0], o["cells_cw"]["y"][0], o["n"])
                 for o in self.prm["overlays"]}
        step = tg.FO4_VERTEX_UNITS / tg.UNITS_PER_METRE
        for e in self.plan:
            ft = tiles[e["anchor"]["ref"]]
            for p in e["points"]:
                x, y = ft.to_cw(p["x"], p["y"])
                self.assertAlmostEqual(x / step, round(x / step), places=2)   # every point is an FO4 vertex
                self.assertAlmostEqual(y / step, round(y / step), places=2)

    def test_seam_pairs_both_sides(self):
        exp = jload(os.path.join(self.out, "expected.json"))
        seam_pts = [p for pts in exp["points"].values() for p in pts if p["kind"] == "seam"]
        self.assertEqual(len(seam_pts), 24)
        for p in seam_pts:
            lo, hi = mco.DIST[p["distance_class"]]
            self.assertTrue(lo <= p["distance_to_seam_m"] <= hi, p)
        by = {}
        for p in seam_pts:
            by.setdefault((p["seam"], p["distance_class"]), {})[p["side"]] = p
        self.assertEqual(len(by), 12)
        for (seam, cls), d in by.items():
            self.assertEqual(set(d), {"a", "b"})
            along = "y_cw" if seam.count("|") else "x_cw"           # 'x' seams (|) pair along y
            self.assertEqual(d["a"][along], d["b"][along])
            self.assertNotEqual(d["a"]["tile"], d["b"]["tile"])

    def test_offline_check_passes(self):
        ok, rep = mco.check_staging(self.out, self.prm, self.plan, None, plugins=False)
        failed = [c for c in rep["checks"] if not c[1]]
        self.assertTrue(ok, failed[:5])
        self.assertEqual(rep["summary"]["failed"], 0)
        self.assertTrue(all(s["bad"] == 0 for s in rep["seams"]))
        self.assertLessEqual(rep["summary"]["max_point_error_mm"], rep["summary"]["step_mm"])

    def test_strips_equal_one_resample(self):
        """Large overlays are resampled in row strips; the result must be the same as one call, bit for bit."""
        fo4 = mco.Fo4Heights(npz=self.npz)
        t = og.Tile(0, 0, -5, -5, 5)
        whole = mco.tile_heights(fo4, t)
        got = np.full_like(whole, np.nan)
        for r0, h in mco.tile_strips(fo4, t, rows=100):            # 640 rows: six strips of 100 and one of 40
            got[r0:r0 + h.shape[0]] = h
        self.assertTrue((got == whole).all())

    def test_decode_window_matches_full_grid(self):
        rng = np.random.default_rng(5)
        raw = rng.integers(0, 65535, size=(3 * 128, 3 * 128)).astype(np.uint16)
        hmin, hmax = -40.0, 299.0
        full = hmin + raw.astype(np.float64) / 65535.0 * (hmax - hmin)
        o = tg.grid_origin(3)
        pts = [(o, o), (o + 299.9, o + 299.9), (o - 5.0, 12.3), (151.0, o + 400.0), (0.0, 0.0)]
        pts += [tuple(v) for v in rng.uniform(o - 2, o + 302, size=(40, 2))]
        for x, y in pts:
            a = mco.decode_at(raw, hmin, hmax, 3, x, y)
            b = tg.point_interp(full, o, o, tg.SF_STEP_M, x, y)
            for k in b:
                self.assertAlmostEqual(a[k], b[k], places=9)

    def test_single_overlay(self):
        """Option (a): a tile at least as large as the region gives one overlay, ring on all four edges, no seams."""
        out = os.path.join(self.tmp.name, "single")
        os.makedirs(out)
        with contextlib.redirect_stdout(io.StringIO()):
            mco.build(build_args(out, self.npz, tile=10, prefix="FO4CWS", experiment="terrain_single", pad="origin",
                                 grid_points=2))
        prm = jload(os.path.join(out, "overlays_params.json"))
        plan = jload(os.path.join(out, "plan.json"))
        self.assertEqual(len(prm["overlays"]), 1)
        o = prm["overlays"][0]
        self.assertEqual((o["n"], o["cells_cw"]), (10, {"x": [-5, 4], "y": [-5, 4]}))
        self.assertEqual(o["mask_outer_edges"], ["w", "e", "s", "n"])
        self.assertEqual(o["planet_target_cell"], [0, 0])          # the region's centre = the overlay's own origin
        self.assertEqual(o["origin_cw_m"], [0.0, 0.0])             # pad origin: local frame = CW frame
        self.assertEqual(len(plan), 1)
        self.assertEqual(sum(1 for p in plan[0]["points"] if p["label"].startswith("grid_T00_")), 4)
        ok, rep = mco.check_staging(out, prm, plan, None, plugins=False)
        self.assertTrue(ok, [c for c in rep["checks"] if not c[1]][:5])
        self.assertEqual(rep["seams"], [])

    def test_check_catches_a_wrong_expectation(self):
        plan = json.loads(json.dumps(self.plan))
        plan[0]["points"][0]["expect"] += 0.05
        ok, rep = mco.check_staging(self.out, self.prm, plan, None, plugins=False)
        self.assertFalse(ok)

    def test_check_catches_a_seam_step(self):
        o = self.prm["overlays"][1]
        path = os.path.join(self.out, *o["btd_file"].split("/"))
        orig = rbytes(path)
        try:
            t = btd.read(orig)
            raw = t.heights_raw.astype(np.int64)
            raw[:, 0] = np.clip(raw[:, 0] + 3000, 0, 65535)          # a 3000-step cliff along the west seam
            t.heights_raw = raw.astype(np.uint16)
            with open(path, "wb") as f:
                f.write(btd.write(t))
            ok, rep = mco.check_staging(self.out, self.prm, self.plan, None, plugins=False)
            self.assertFalse(ok)
            self.assertTrue(any(s["bad"] > 0 for s in rep["seams"]))
        finally:
            with open(path, "wb") as f:
                f.write(orig)


if __name__ == "__main__":
    unittest.main()
