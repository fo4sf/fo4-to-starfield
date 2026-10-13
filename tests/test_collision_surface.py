"""scripts/terrain/collision_surface.py on synthetic shapes: rotation conventions, the vertical ray, the dropped
sphere (faces, edges, vertices), exhaustive reference selection, a whole synthetic staging (a tilted bar that covers a
point under one convention and not the other: the northeast probe in miniature), runner readings, the clear-point
search and FO4's precombined instance transforms."""
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import contextlib
import io
import unittest

import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "tests"))
spec = importlib.util.spec_from_file_location("collision_surface", root / "scripts" / "terrain" / "collision_surface.py")
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)
from fo4sf import btd, exterior, nif, sfnif  # noqa: E402
from test_sfbodies import convex_blob, cube  # noqa: E402


def quad(z, x0=-5.0, y0=-5.0, x1=5.0, y1=5.0):
    """Two triangles of a horizontal rectangle at height z."""
    a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
    return np.array([(a, b, c), (a, c, d)], np.float64)


def _box(x0, y0, z0, x1, y1, z1):
    c = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [t for q in quads for t in ((c[q[0]], c[q[1]], c[q[2]]), (c[q[0]], c[q[2]], c[q[3]]))]


def closest_on_triangle(p, a, b, c):
    """Closest point to p on triangle abc (Ericson, Real-Time Collision Detection 5.1.5): the test's own oracle."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = ab @ ap, ac @ ap
    if d1 <= 0 and d2 <= 0:
        return a
    bp = p - b
    d3, d4 = ab @ bp, ac @ bp
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return a + d1 / (d1 - d3) * ab
    cp = p - c
    d5, d6 = ab @ cp, ac @ cp
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return a + d2 / (d2 - d6) * ac
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        return b + (d4 - d3) / ((d4 - d3) + (d5 - d6)) * (c - b)
    denom = 1.0 / (va + vb + vc)
    return a + ab * (vb * denom) + ac * (vc * denom)


def dist_to_tris(p, tris):
    return min(float(np.linalg.norm(p - closest_on_triangle(p, *t))) for t in tris)


class RotationTests(unittest.TestCase):
    def test_xyz_is_exterior_ref_matrix(self):
        for rot in ((0.1, -0.2, 3.0), (0.031172026, -0.21233042, 3.1979096), (-1.2, 0.7, 5.5)):
            m = np.array(exterior.ref_matrix(rot)).reshape(3, 3)
            self.assertTrue(np.allclose(cs.rotation(rot, "xyz"), m, atol=1e-12))

    def test_zyx_composes_z_first(self):
        rot = (0.3, -0.4, 1.1)
        expect = cs._rx(-0.3) @ cs._ry(0.4) @ cs._rz(-1.1)
        self.assertTrue(np.allclose(cs.rotation(rot, "zyx"), expect))
        self.assertFalse(np.allclose(cs.rotation(rot, "zyx"), cs.rotation(rot, "xyz"), atol=1e-3))

    def test_a_heading_alone_is_the_same_in_every_order(self):
        rot = (0.0, 0.0, 2.2)
        for c in ("xyz", "xzy", "yxz", "yzx", "zxy", "zyx"):
            self.assertTrue(np.allclose(cs.rotation(rot, c), cs.rotation(rot, "zyx")))
        v = cs.rotation((0, 0, math.pi / 2), "zyx") @ np.array([1.0, 0.0, 0.0])
        self.assertTrue(np.allclose(v, [0.0, -1.0, 0.0]))              # clockwise heading: +x turns to -y

    def test_unknown_convention_raises(self):
        with self.assertRaises(ValueError):
            cs.rotation((0, 0, 0), "xxz")
        self.assertIn("Z applied first", cs.describe_convention("zyx"))
        self.assertIn("Y applied first", cs.describe_convention("yxz"))


class RayTests(unittest.TestCase):
    def test_box_hits_highest_first_and_edge_on_faces_ignored(self):
        t = np.array(_box(0, 0, 1, 2, 2, 3), np.float64)
        hits = cs.ray_hits(t, 1.0, 0.5)
        self.assertEqual([round(z, 6) for z, _ in hits], [3.0, 1.0])   # top and bottom; the walls are edge-on
        self.assertEqual(cs.ray_hits(t, 5.0, 5.0), [])
        on_edge = cs.ray_hits(quad(2.0, 0, 0, 1, 1), 1.0, 0.5)          # a point on the rectangle's border counts
        self.assertTrue(on_edge and abs(on_edge[0][0] - 2.0) < 1e-12)

    def test_slope(self):
        self.assertAlmostEqual(cs.slope_deg(quad(1.0)[0]), 0.0)
        tri = [(0, 0, 0), (1, 0, 1), (0, 1, 0)]
        self.assertAlmostEqual(cs.slope_deg(tri), 45.0)


class SphereTests(unittest.TestCase):
    def test_floor(self):
        zc, i = cs.sphere_drop(quad(1.0), 0.0, 0.0, 0.4)
        self.assertAlmostEqual(zc - 0.4, 1.0, places=9)

    def test_slope_feet_above_the_surface(self):
        th = math.radians(30)
        t = np.array([[(-5, -5, -5 * math.tan(th)), (5, -5, 5 * math.tan(th)), (5, 5, 5 * math.tan(th))],
                      [(-5, -5, -5 * math.tan(th)), (5, 5, 5 * math.tan(th)), (-5, 5, -5 * math.tan(th))]])
        zc, _ = cs.sphere_drop(t, 0.0, 0.0, 0.4)
        self.assertAlmostEqual(zc - 0.4, 0.4 * (1 / math.cos(th) - 1), places=9)

    def test_edge_beside_the_axis(self):
        t = quad(1.0, 0.2, -1.0, 2.0, 1.0)                             # top starts 0.2 m east of the axis
        zc, _ = cs.sphere_drop(t, 0.0, 0.0, 0.4)
        self.assertAlmostEqual(zc, 1.0 + math.sqrt(0.16 - 0.04), places=9)
        self.assertEqual(cs.sphere_drop(t, -0.5, 0.0, 0.4), (None, None))   # 0.7 m away: no contact
        self.assertEqual(cs.sphere_drop(t, -0.5, 0.0, 0.0), (None, None))   # radius 0 = the ray

    def test_vertex_tip(self):
        tip = (0.3, 0.0, 2.0)
        t = np.array([[tip, (1.3, -1, 0), (1.3, 1, 0)], [tip, (1.3, 1, 0), (-0.7, 0, 0)],
                      [tip, (-0.7, 0, 0), (1.3, -1, 0)]], np.float64)
        zc, _ = cs.sphere_drop(t, 0.0, 0.0, 0.5)
        self.assertGreaterEqual(zc, 2.0 + math.sqrt(0.25 - 0.09) - 1e-9)

    def test_contact_is_exact_against_a_closest_point_oracle(self):
        rng = np.random.default_rng(7)
        for _ in range(60):
            t = rng.uniform(-1.5, 1.5, size=(4, 3, 3))
            r = float(rng.uniform(0.1, 0.8))
            zc, _ = cs.sphere_drop(t, 0.0, 0.0, r)
            if zc is None:
                self.assertGreater(min(dist_to_tris(np.array([0, 0, z]), t) for z in np.linspace(-5, 5, 201)), r - 0.06)
                continue
            self.assertAlmostEqual(dist_to_tris(np.array([0.0, 0.0, zc]), t), r, places=6)   # touching
            self.assertGreater(dist_to_tris(np.array([0.0, 0.0, zc + 1e-4]), t), r)          # free just above

    def test_terrain_sphere_on_flat_and_sloped_ground(self):
        class Plane:
            def __init__(self, k):
                self.k = k

            def bilinear(self, xs, ys):
                return self.k * np.asarray(xs, np.float64) + 5.0

            def ground(self, x, y):
                return float(self.bilinear([x], [y])[0])
        self.assertAlmostEqual(cs.terrain_sphere(Plane(0.0), 0, 0, 0.4) - 0.4, 5.0, places=9)
        k = math.tan(math.radians(30))
        feet = cs.terrain_sphere(Plane(k), 0, 0, 0.4) - 0.4
        self.assertAlmostEqual(feet - 5.0, 0.4 * (1 / math.cos(math.radians(30)) - 1), delta=0.002)   # sampled
        self.assertEqual(cs.terrain_sphere(Plane(k), 1.0, 0, 0.0), 5.0 + k)


# ------------------------------------------------------------------------------------------- a synthetic staging
GROUND = 10.0
BAR = ((0.0, -0.5, 0.0), (10.0, 0.5, 0.5))           # model space: a 10 m bar along +x, 0.5 m high
BAR_POS = (0.0, 0.0, GROUND + 1.0)
BAR_ROT = (0.0, -0.3, math.pi / 2)                    # heading 90 (bar along -y) with a Y tilt
P = (0.0, -8.0)                                       # 8 m along the bar


def make_staging(tmp, refs=None):
    """objects.json, Data\\meshes\\rocks\\bar.nif (a convex box on the root, named with a backslash as objects.json
    names models), Data\\meshes\\bush.nif (no collision), Data\\Terrain\\W.btd (flat at GROUND)."""
    os.makedirs(os.path.join(tmp, "Data", "meshes", "rocks"))
    os.makedirs(os.path.join(tmp, "Data", "Terrain"))
    v, f = cube(*BAR)
    with open(os.path.join(tmp, "Data", "meshes", "rocks", "bar.nif"), "wb") as fh:
        fh.write(nif.serialize(sfnif.build_static_nif(b"Bar", [], collision_blob=convex_blob(v, f))))
    with open(os.path.join(tmp, "Data", "meshes", "bush.nif"), "wb") as fh:
        fh.write(nif.serialize(sfnif.build_static_nif(b"Bush", [])))
    n = 2
    raw = np.full((n * 128, n * 128), 10000, np.uint16)          # 10000 / 65535 * 65.535 = 10.0 m
    t = btd.Btd(1, 0.0, 65.535, [0], raw, np.zeros_like(raw), np.zeros((n * 2, n * 2, 8), np.uint8))
    with open(os.path.join(tmp, "Data", "Terrain", "W.btd"), "wb") as fh:
        fh.write(btd.write(t))
    bases = [{"edid": "T_bar", "model": "rocks\\bar.nif", "source": "meshes\\Bar.nif", "collision": "fo4-native"},
             {"edid": "T_bush", "model": "bush.nif", "source": "meshes\\Bush.nif", "collision": "fo4-none"}]
    if refs is None:
        refs = [{"src": "000001:T.esm", "base": 0, "pos": list(BAR_POS), "rot": list(BAR_ROT), "scale": 1.0,
                 "disabled": False},
                {"src": "000002:T.esm", "base": 1, "pos": [0.0, -8.0, GROUND], "rot": [0, 0, 0], "scale": 1.0,
                 "disabled": False},
                {"src": "000003:T.esm", "base": 0, "pos": [0.0, -8.0, GROUND + 5], "rot": [0, 0, 0], "scale": 1.0,
                 "disabled": True}]
    with open(os.path.join(tmp, "objects.json"), "w", encoding="utf-8") as fh:
        json.dump({"world": "W", "bases": bases, "refs": refs}, fh)
    with open(os.path.join(tmp, "formids.json"), "w", encoding="utf-8") as fh:
        json.dump({"plugin": "T.esm", "bases": {"T_bar": "000800"}, "refs": {"000001:T.esm": "000801"}}, fh)
    return tmp


class StagingTests(unittest.TestCase):
    def test_tilted_bar_covers_the_point_under_zyx_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = cs.Staging(make_staging(tmp))
            self.assertAlmostEqual(st.terrain.ground(*P), GROUND, places=5)   # BTD range is float32
            pts, sel = cs.trace_points(st, [{"label": "p", "x": P[0], "y": P[1]}], ("xyz", "zyx"), 100.0, (0.3,),
                                       cache=os.path.join(tmp, "bounds.json"))
            self.assertEqual(sel["placed"], 1)                                # the bush has no collision
            self.assertEqual(sel["disabled"], ["000003:T.esm"])
            zyx, xyz = pts[0]["conventions"]["zyx"], pts[0]["conventions"]["xyz"]
            self.assertEqual(zyx["support_kind"], "object")
            # level along the bar; its 0.5 m top is tilted 0.3 rad across the bar: 0.5 / cos(0.3) on the centre line
            self.assertAlmostEqual(zyx["support"], BAR_POS[2] + 0.5 / math.cos(0.3), places=4)
            self.assertEqual(zyx["top"]["ref"], "000001:T.esm")
            self.assertEqual(zyx["top"]["body"]["shape"], "hknpConvexShape")
            self.assertEqual((zyx["top"]["refr_in_plugin"], zyx["top"]["base_in_plugin"]), ("000801", "000800"))
            self.assertEqual(zyx["top"]["model_sha256"], cs.sha256(st.model_path(0)))
            self.assertEqual(zyx["spheres"]["0.3"]["kind"], "object")
            self.assertEqual(xyz["support_kind"], "terrain")                  # X first: the bar dips into the ground
            self.assertAlmostEqual(xyz["support"], GROUND, places=4)
            self.assertTrue(os.path.exists(os.path.join(tmp, "bounds.json")))
            # the cache is reused (same size and mtime): radii unchanged, nothing re-read
            st2 = cs.Staging(tmp)
            r = st2.radii(os.path.join(tmp, "bounds.json"))
            self.assertAlmostEqual(r[0], math.sqrt(10 ** 2 + 0.5 ** 2 + 0.5 ** 2), places=5)
            self.assertEqual(r[1], 0.0)
            self.assertEqual(st2.models, {})

    def test_selection_is_by_collision_radius_not_origin_distance(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = cs.Staging(make_staging(tmp))
            radii = st.radii()
            # 9.9 m from the bar origin: only a radius-based selection keeps it
            placed, disabled, bad = cs.select_refs(st, radii, [(0.0, -9.9)], 0.1)
            self.assertEqual(placed, [0])
            self.assertEqual(disabled, [2])
            placed, _, _ = cs.select_refs(st, radii, [(0.0, -10.2 - 0.6)], 0.1)
            self.assertEqual(placed, [])

    def test_unreadable_model_makes_the_point_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_staging(tmp)
            with open(os.path.join(tmp, "Data", "meshes", "rocks", "bar.nif"), "wb") as fh:
                fh.write(b"not a nif")
            st = cs.Staging(tmp)
            pts, sel = cs.trace_points(st, [{"label": "p", "x": P[0], "y": P[1]}], ("zyx",))
            self.assertEqual(pts[0]["status"], "INCONCLUSIVE")
            self.assertEqual(pts[0]["unreadable_refs"], ["000001:T.esm"])      # the disabled one has no collision
            self.assertEqual(sel["disabled"], ["000003:T.esm"])
            self.assertTrue(sel["unreadable"])
            with contextlib.redirect_stdout(io.StringIO()):     # no clear point is proposed next to unseen collision
                self.assertEqual(cs.main(["clear", "--staging", tmp, f"--near={P[0]},{P[1]},p", "--search-m", "2"]), 2)

    def test_runner_readings_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_staging(tmp)
            run = os.path.join(tmp, "q", "a1")
            os.makedirs(run)
            off = (-1200.0, -2700.0, 0.0)
            spec_ = {"id": "t0", "kind": "terrain", "z_ref": "zref", "drop_z": 100.0,
                     "points": [{"label": "zref", "x": 5.0, "y": 5.0, "expect": GROUND},
                                {"label": "p", "x": P[0], "y": P[1], "expect": GROUND}]}
            obs = {"offset": list(off), "points": [
                {"label": "zref", "read": f"{5 + off[0]:.2f} {5 + off[1]:.2f} {GROUND + 0.02:.2f}"},
                {"label": "p", "read": f"{P[0] + off[0]:.2f} {P[1] + off[1]:.2f} {GROUND + 1.52:.2f}"}]}
            with open(os.path.join(run, "spec.json"), "w", encoding="utf-8") as fh:
                json.dump(spec_, fh)
            with open(os.path.join(run, "obs.json"), "w", encoding="utf-8-sig") as fh:   # the runner writes a BOM
                json.dump(obs, fh)
            pts = cs.runner_points(run)
            self.assertEqual(pts[1]["read_local"], [0.0, -8.0, GROUND + 1.5])
            self.assertEqual(pts[1]["z_shift"], 0.02)
            out = os.path.join(tmp, "report.json")
            with contextlib.redirect_stdout(io.StringIO()):
                code = cs.main(["trace", "--staging", tmp, "--runner-test", run, "--sphere", "0.3", "--out", out])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as fh:
                rep = json.load(fh)
            p = rep["points"][1]
            self.assertTrue(p["conventions"]["zyx"]["vs_read"]["support"]["match"])
            self.assertFalse(p["conventions"]["xyz"]["vs_read"]["support"]["match"])
            self.assertEqual(rep["summary"]["zyx/support"]["within_match_m"], 2)
            self.assertEqual(rep["summary"]["xyz/support"]["within_match_m"], 1)
            self.assertIn("objects.json", rep["pins"])

    def test_clear_finds_open_ground_away_from_the_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_staging(tmp)
            out = os.path.join(tmp, "clear.json")
            with contextlib.redirect_stdout(io.StringIO()):
                code = cs.main(["clear", "--staging", tmp, f"--near={P[0]},{P[1]},p", "--search-m", "6", "--drop-z", "100",
                                "--prev=0,0.5,15", "--next=3,-14", "--out", out])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as fh:
                pt = json.load(fh)["point"]
            st = cs.Staging(tmp)
            for conv in ("xyz", "zyx"):
                w = cs.PlacedWorld(st, [0], conv)
                lo = w.tris.reshape(-1, 3).min(axis=0)
                hi = w.tris.reshape(-1, 3).max(axis=0)
                gap = math.hypot(max(lo[0] - pt["x"], 0, pt["x"] - hi[0]), max(lo[1] - pt["y"], 0, pt["y"] - hi[1]))
                self.assertGreaterEqual(gap, cs.CLEAR_M - 1e-9, conv)        # nothing within 2 m in either order
                self.assertEqual(pt["per_convention"][conv]["landing"], GROUND)
                self.assertFalse(any(q["hits"] for q in pt["per_convention"][conv]["teleport_in"]))
            self.assertAlmostEqual(pt["expect"], GROUND, places=4)
            self.assertIsNone(cs.clear_ok(cs.PlacedWorld(st, [0], "zyx"), P[0], P[1], 100.0))   # on the bar


# ------------------------------------------------------------------------------------- FO4 precombine instances
def packed_block(datas):
    """A BSPackedCombinedSharedGeomDataExtra block body: datas = [[(rot9, translation, scale), ...], ...]."""
    b = struct.pack("<i", -1) + struct.pack("<Q", 0) + struct.pack("<5I", 0, 0, 0, 0, len(datas))
    b += b"".join(struct.pack("<II", 0x1000 + k, 0) for k in range(len(datas)))
    for data in datas:
        b += struct.pack("<8I", 3, 1, 1, 0, 0, 0, 0, 0) + struct.pack("<I", len(data))
        for rot, tr, sc in data:
            b += struct.pack("<f", 1.0) + struct.pack("<9f", *rot) + struct.pack("<3f", *tr) + struct.pack("<f", sc)
            b += struct.pack("<4f", 0, 0, 0, 1)
        b += struct.pack("<Q", 0)
    return b


class PrecombineTests(unittest.TestCase):
    def test_parse_and_compare(self):
        refs = [{"src": "A", "pos": [1.0, 2.0, 3.0], "rot": [0.2, -0.3, 1.0], "scale": 1.0},
                {"src": "B", "pos": [10.0, 2.0, 3.0], "rot": [-0.1, 0.25, 4.0], "scale": 0.8},
                {"src": "C", "pos": [20.0, 2.0, 3.0], "rot": [0.0, 0.1, 0.0], "scale": 1.0},     # two instances here
                {"src": "D", "pos": [30.0, 2.0, 3.0], "rot": [0.0, 0.1, 0.0], "scale": 1.0}]     # not precombined
        inst = lambda r: (tuple(cs.rotation(r["rot"], "zyx").reshape(-1)), tuple(np.array(r["pos"]) * 70.0), r["scale"])
        blk = packed_block([[inst(refs[0]), inst(refs[2])], [inst(refs[1]), inst(refs[2])]])
        got = cs.packed_instances(blk)
        self.assertEqual(len(got), 4)
        self.assertAlmostEqual(got[2][2], 0.8, places=6)
        res = cs.compare_rotations(refs, got, ("xyz", "zyx"))
        self.assertEqual((res["matched"], res["ambiguous"], res["unmatched"]), (2, 1, 1))
        self.assertEqual(res["conventions"]["zyx"]["exact"], 2)
        self.assertEqual(res["conventions"]["xyz"]["exact"], 0)
        self.assertIn("xyz", res["examples"])
        with self.assertRaises(ValueError):
            cs.packed_instances(blk[:-3])
        with self.assertRaises(ValueError):
            cs.packed_instances(blk + b"\0\0\0\0")


if __name__ == "__main__":
    unittest.main()
