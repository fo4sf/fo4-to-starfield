"""core64c builder (scripts/terrain/make_core64c.py): band selection, size measurement, BTD decoding, local world
queries, plan entries and ordering, hard-linked staging and the archive estimate, all on synthetic data."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "scripts" / "terrain"))
sys.path.insert(0, str(root / "tests"))
spec = importlib.util.spec_from_file_location("make_core64c", root / "scripts" / "terrain" / "make_core64c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
from fo4sf import btd, exterior, textures  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402


def ref(fk, typ="Static", model="Architecture\\A.nif", pos=(0.0, 0.0, 0.0), **kw):
    r = {"formkey": fk, "type": typ, "base_editor_id": "E" + fk[:6], "base_formkey": "000001:Fallout4.esm",
         "model": model, "pos": list(pos), "rot": [0.0, 0.0, 0.0], "scale": 1, "disabled": 0, "persistent": False,
         "exterior_cell": [0, 0], "enable_parent": None, "linked_references": [], "ownership": None}
    r.update(kw)
    return r


def box_tris(x0, y0, z0, x1, y1, z1):
    c = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [t for q in quads for t in ((c[q[0]], c[q[1]], c[q[2]]), (c[q[0]], c[q[2]], c[q[3]]))]


def synthetic_btd(path, n=2, hmin=-10.0, hmax=90.0, seed=1):
    rng = np.random.default_rng(seed)
    raw = rng.integers(0, 65535, size=(n * 128, n * 128), dtype=np.uint16)
    t = btd.Btd(1, hmin, hmax, [0], raw, np.zeros_like(raw), np.zeros((n * 2, n * 2, 8), np.uint8))
    with open(path, "wb") as f:
        f.write(btd.write(t))
    return raw


def local_world(objects, ground=0.0, origin=-100.0, size=256):
    """A CoreWorld without files: flat terrain at `ground` from `origin` (both axes) and box objects
    [(src, box)] placed at the origin."""
    w = mk.CoreWorld.__new__(mk.CoreWorld)
    w.bases, w.placed, tris, owners = [], [], [], []
    for k, (src, box) in enumerate(objects):
        w.bases.append({"edid": "FO4Core_" + src.lower(), "model": src.lower() + ".nif", "collision": "fo4-native"})
        w.placed.append({"src": src, "base": k, "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": 1.0,
                         "disabled": False})
        t = box_tris(*box)
        tris += t
        owners += [k] * len(t)
    w.tris, w.owners = np.array(tris, np.float64).reshape(-1, 3, 3), np.array(owners, np.int64)
    w.index = exterior.SurfaceIndex(w.tris, w.owners)
    w.heights = np.full((size, size), ground, np.float64)
    w.ox = w.oy = origin
    w.step, w.hmin, w.n = 0.004, ground - 50.0, 1
    w.by_src = {p["src"]: k for k, p in enumerate(w.placed)}
    return w


class SelectTests(unittest.TestCase):
    def test_bands_slimmed_and_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            b1 = {"exterior": {"cells": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]},
                  "refs": [ref("000001:Fallout4.esm"), ref("000002:Fallout4.esm", typ="Light"),
                           ref("000003:Fallout4.esm", model="Effects\\Fog.nif")],
                  "deferred_refs": [{"formkey": "000009:Fallout4.esm", "type": "PlacedNpc", "reason": "actor"}]}
            b2 = {"exterior": {"cells": [{"x": 0, "y": 1}]},
                  "refs": [ref("000004:Fallout4.esm", model="architecture\\a.nif"), ref("000005:Fallout4.esm",
                                                                                      model="Water\\Water1024.nif")]}
            paths = []
            for k, b in enumerate((b1, b2)):
                p = os.path.join(tmp, f"band_{k}.json")
                with open(p, "w") as f:
                    json.dump(b, f)
                paths.append(p)
            kept, skipped, tot = mk.select_bands(paths)
            self.assertEqual(tot, {"bands": 2, "cells": 3, "refs": 5, "deferred": 1})
            self.assertEqual([r["formkey"] for r in kept], ["000001:Fallout4.esm", "000004:Fallout4.esm"])
            self.assertEqual(set(kept[0]), set(mk.SLIM_KEYS) | {"enable_parent"})
            self.assertEqual(exterior.reason_counts(skipped), {"type_not_translated": 1, "effect": 1, "deferred": 1,
                                                               "water": 1})
            self.assertEqual(len(kept) + len(skipped), tot["refs"] + tot["deferred"])
            # one model, two references (case differs): one convert_batch entry
            self.assertEqual(len(mk.convert_list(kept)), 1)

    def test_a_reference_in_two_bands_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for k in range(2):
                p = os.path.join(tmp, f"band_{k}.json")
                with open(p, "w") as f:
                    json.dump({"refs": [ref("000001:Fallout4.esm")]}, f)
                paths.append(p)
            with self.assertRaises(ValueError):
                mk.select_bands(paths)

    def test_regions(self):
        self.assertEqual(mk.region_of((-1, 15)), (-1, 0))
        self.assertEqual(mk.region_of((16, -17)), (1, -2))


class MeasureTests(unittest.TestCase):
    def test_bc_size_matches_cap_dds(self):
        from test_texture_cap import bc_dds
        for fmt, dxgi, bb in (("BC1", 71, 8), ("BC5", 83, 16), ("BC4", 80, 8)):
            for w, h, cap in ((64, 64, 0), (64, 32, 16), (128, 64, 128), (32, 128, 8)):
                data = bc_dds(w, h, dxgi=dxgi, bb=bb)
                out, _ = textures.cap_dds(data, cap)
                self.assertEqual(mk.bc_size(fmt, w, h, cap=cap), len(out), (fmt, w, h, cap))

    def test_dry_converter_outputs(self):
        class Entry:
            def __init__(self, w, h):
                self.width, self.height = w, h

        class Arc:
            names = {"textures/a_d.dds": Entry(1024, 512), "textures/a_n.dds": Entry(512, 512),
                     "textures/a_s.dds": Entry(256, 256)}

            def __init__(self):
                self.entries = list(self.names.values())
                self.idx = {k: i for i, k in enumerate(self.names)}

            def find(self, n):
                return self.idx.get(n.replace("\\", "/").lower())

        src = type("Src", (), {"textures": [Arc()]})()
        dry = mk.DryConverter(src)
        dry._texture_set("set1", "a_d.dds", "a_n.dds", "a_s.dds", alpha_test=True)
        dry._texture_set("set2", "a_d.dds", "a_n.dds", "")
        self.assertEqual(dry.outputs["set1"], [("color", "BC1", 1024, 512), ("normal", "BC5", 512, 512),
                                               ("rough", "BC4", 256, 256), ("opacity", "BC4", 1024, 512)])
        self.assertEqual(dry.outputs["set2"][2], ("rough", "BC4", 128, 128))      # no spec: a quarter of the normal
        with self.assertRaises(FileNotFoundError):
            dry._texture_set("set3", "missing_d.dds", "a_n.dds", "")


class TerrainTests(unittest.TestCase):
    def test_bilinear_and_window_match_point_interp(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "t.btd")
            raw = synthetic_btd(p)
            t = mk.Terrain(p)
            full = t.hmin + raw.astype(np.float64) / 65535.0 * (t.hmax - t.hmin)
            o = tg.grid_origin(2)
            rng = np.random.default_rng(2)
            xs, ys = rng.uniform(-100, 99, 50), rng.uniform(-100, 99, 50)
            got = t.bilinear(xs, ys)
            win, ox, oy = t.window(-40, -30, 20, 35)
            w = mk.CoreWorld.__new__(mk.CoreWorld)
            w.heights, w.ox, w.oy = win, ox, oy
            for x, y, g in zip(xs, ys, got):
                want = tg.point_interp(full, o, o, tg.SF_STEP_M, x, y)
                self.assertAlmostEqual(g, want["bilinear"], places=9)
                if -40 <= x <= 20 and -30 <= y <= 35:
                    got_all = w.ground_all(x, y)
                    for rule in want:
                        self.assertAlmostEqual(got_all[rule], want[rule], places=9)
            # outside the grid: clamped like point_interp
            self.assertAlmostEqual(t.bilinear([-500.0], [500.0])[0],
                                   tg.point_interp(full, o, o, tg.SF_STEP_M, -500.0, 500.0)["bilinear"], places=9)


class WorldTests(unittest.TestCase):
    def test_segment_blocked(self):
        w = local_world([("WALL", (10, -5, 0, 11, 5, 4)), ("LANDMARK", (20, -2, 0, 24, 2, 6))])
        self.assertTrue(w.segment_blocked((0, 0, 1.7), (22, 0, 3)))                    # through the wall
        self.assertFalse(w.segment_blocked((0, 0, 1.7), (22, 0, 3), ignore={0, 1}))
        self.assertFalse(w.segment_blocked((0, 8, 1.7), (22, 8, 3)))                   # beside it
        self.assertTrue(w.segment_blocked((0, 8, 1.7), (22, 8, -1)))                   # under the terrain

    def test_object_top_and_view_spot(self):
        w = local_world([("ROOF", (-5, 20, 0, 5, 30, 4.0)), ("TREE", (-1, 0, 0, 1, 2, 8))])
        top = mk.object_top(w, w.by_src["ROOF"], "roof", 100.0)
        self.assertEqual(top["kind"], "object_top")
        self.assertAlmostEqual(top["expect"], 4.0)
        self.assertGreaterEqual(top["discrimination"], 3.9)
        v = mk.view_spot(w, "view_roof", ("ROOF",), 100.0)
        self.assertEqual(v["kind"], "view")
        self.assertLess(v["y"], 20)                                                     # south of the roof
        self.assertFalse(w.segment_blocked((v["x"], v["y"], 1.7), v["target"], ignore={0}))
        self.assertGreaterEqual(math.hypot(v["x"], v["y"] - 1) if abs(v["x"]) < 2 else 99, 1.0)

    def test_entry_drop_clears_tops(self):
        w = local_world([("TALL", (-1, -1, 0, 1, 1, 30))])
        pts = [{"label": "a", "x": 0.0, "y": 0.0, "expect": 30.0}, {"label": "b", "x": 50.0, "y": 0.0, "expect": 0.0}]
        self.assertEqual(mk.entry_drop(w, pts), 70.0)                                  # 30 + 40
        pts[0]["expect"] = 0.0                                                          # 1 m from a 30 m top
        pts[0]["x"] = 1.5
        self.assertEqual(mk.entry_drop(w, pts), 40.0)                                   # max(0 + 40, 30 + 10)


class PlanTests(unittest.TestCase):
    def test_spoke_order_needs_no_more_waypoints_than_the_spokes(self):
        start = (0.0, 0.0, 0.0)
        pts = []
        for deg in (0, 45, 135, 180, 270, 320):                    # core64's six rays, probes at 200 and 500 m
            for d in (200, 500):
                a = math.radians(deg)
                pts.append({"label": f"r{deg}_{d}", "x": d * math.cos(a), "y": d * math.sin(a), "expect": 0.0})
        order = mk.order_entry(start, pts)                          # 12 points: spoke zig-zag + 2-opt
        self.assertEqual(sorted(p["label"] for p in order), sorted(p["label"] for p in pts))
        key = mk.seq_key(start, order)
        self.assertLessEqual(key, mk.seq_key(start, mk.spoke_order(start, pts)))
        self.assertLess(key[0], mk.seq_key(start, sorted(pts, key=lambda p: p["label"]))[0])

    def test_exhaustive_order_fewest_waypoints_then_shortest(self):
        pts = [{"label": "a", "x": -200.0, "y": 0.0, "expect": 0.0}, {"label": "b", "x": 250.0, "y": 0.0, "expect": 0.0}]
        # a then b: 200 m (1 waypoint) + 450 m (2) = 3, 650 m; b then a: 250 m (1) + 450 m (2) = 3, 700 m
        self.assertEqual([p["label"] for p in mk.order_entry((0.0, 0.0, 0.0), pts)], ["a", "b"])
        self.assertEqual(mk.seq_key((0.0, 0.0, 0.0), pts), (3, 0, 650.0))
        self.assertEqual([mk.waypoints_needed(d) for d in (0.0, 185.0, 185.1, 370.0, 371.0)], [0, 0, 1, 1, 2])

    def test_plan_entry_and_validation(self):
        base = {"coc": "FO4Core_RedRocketSpawn", "label": "core64", "spawn_local": [1, 2, 3], "z_ref": "arrival",
                "drop_z": 150.0, "settle_ms": 10000, "points": []}
        pts = [{"label": "zref_ground", "x": 1.0, "y": 2.0, "expect": 3.0, "kind": "terrain_ref"},
               {"label": "roof", "x": 4.0, "y": 5.0, "expect": 9.0, "kind": "object_top"}]
        e = mk.plan_entry(base, "core64c", 160.0, pts, "zref_ground", [1, 2, 3.1], 11000)
        self.assertEqual(e["coc"], base["coc"])
        self.assertEqual(e["settle_ms"], 11000)
        self.assertEqual(e["points"][1], {"label": "roof", "x": 4.0, "y": 5.0, "expect": 9.0})
        kinds = {(0, p["label"]): p["kind"] for p in pts}
        self.assertEqual((e["hop_m"], e["hop_wait_ms"]), (mk.HOP_M, mk.HOP_WAIT_MS))
        self.assertEqual(mk.validate_plan([e], base, kinds), [])
        bad = dict(e, z_ref="roof", extra=1)
        probs = mk.validate_plan([bad], base, kinds)
        self.assertTrue(any("extra" in p for p in probs) and any("z_ref" in p for p in probs))
        self.assertTrue(mk.validate_plan([dict(e, coc="Other")], base, kinds))

    def test_order_avoids_teleport_positions_in_objects(self):
        # setpos x comes first: from the start, going to "a" stands the player in the thin wall at (30, 0) on the
        # ground; going to "b" first, and then from b (0, 40) to a, passes north of the wall
        w = local_world([("WALL", (29.8, -3.0, 0.0, 30.2, 3.0, 5.0))], ground=0.0, origin=-100.0, size=256)
        legs = mk.Legs(w, (0.0, 0.0), 50.0)
        a = {"label": "a", "x": 30.0, "y": 40.0, "expect": 0.0}
        b = {"label": "b", "x": 0.0, "y": 40.0, "expect": 0.0}
        self.assertGreater(legs((0.0, 0.0, 0.0), a)["cost"], 0)                  # (30, 0, 0) is inside the wall
        self.assertEqual(legs((0.0, 0.0, 0.0), b)["cost"], 0)
        self.assertEqual([p["label"] for p in mk.order_entry((0.0, 0.0, 0.0), [a, b], legs)], ["b", "a"])
        self.assertEqual([p["label"] for p in mk.order_entry((0.0, 0.0, 0.0), [a, b])], ["b", "a"])  # shorter too
        self.assertEqual(len(legs.memo), 4)

    def test_teleports_as_the_runner_makes_them(self):
        pts = [{"label": "a", "x": 10.0, "y": 0.0}, {"label": "b", "x": 610.0, "y": 0.0},
               {"label": "c", "x": 650.0, "y": 0.0}]
        # no hop before the first point; 600 m -> ceil(600 / 300) = 2 teleports (1 hop); 40 m -> none
        self.assertEqual(mk.runner_teleports(pts, 300), [("a", 10.0, 0.0), (None, 310.0, 0.0), ("b", 610.0, 0.0),
                                                         ("c", 650.0, 0.0)])
        self.assertEqual([t[1] for t in mk.runner_teleports(pts, 200)], [10.0, 210.0, 410.0, 610.0, 650.0])
        self.assertEqual(mk.runner_teleports([{"label": "far", "x": 900.0, "y": 0.0}], 200), [("far", 900.0, 0.0)])
        self.assertEqual(len(mk.runner_teleports(pts, 0)), 3)

    def test_axis_cells_whatever_the_offset(self):
        self.assertEqual([mk.axis_cells(d) for d in (0.0, -0.5, 100.0, 199.99, 200.0, 200.01, -292.6)],
                         [0, 1, 1, 2, 2, 3, 3])
        # core64 e_200m -> e_500m: 292.6 m east, 3 cells in core64's frame (relocated in game); hop_m 200 keeps every
        # teleport at 2 cells or fewer in any frame
        moves = mk.axis_moves((-784.4571, 1148.3429), [("e_500m", -491.8857, 1146.5143)])
        self.assertEqual((moves[0]["cells"], moves[0]["cells_core64"]), (3, 3))
        moves = mk.axis_moves((0.0, 0.0), [("a", 150.0, -20.0)], offset=(-1200.0, -2700.0))
        self.assertEqual((moves[0]["cells"], moves[0]["cells_core64"]), (2, 1))
        moves = mk.axis_moves((-784.4571, 1148.3429), mk.runner_teleports(
            [{"label": "e_200m", "x": -784.4571, "y": 1148.3429}, {"label": "e_500m", "x": -491.8857, "y": 1146.5143}]))
        self.assertEqual([m["to"] for m in moves], ["e_200m", "hop", "e_500m"])
        self.assertLessEqual(max(m["cells"] for m in moves), mk.MAX_AXIS_CELLS)

    def test_travel_time_against_the_step_timeout(self):
        # the old entry 1: 9 points at a 10 s settle and 6 hops: 77 s left; core64b (7 points, 4 hops at 10.5 s): 130 s
        # estimated, 138 s measured (its last point 732 s after the step started)
        self.assertEqual(mk.runner_timeout(9), 1050)
        self.assertEqual(round(mk.runner_seconds(9, 10000, 6)), 973)
        self.assertEqual(round(mk.runner_timeout(7) - mk.runner_seconds(7, 10500, 4)), 130)
        pts = [{"label": f"p{k}", "x": 150.0 * k, "y": 0.0, "expect": 0.0} for k in range(5)]
        t = mk.entry_travel((0.0, 0.0), {"points": pts, "settle_ms": 10000, "hop_m": 200})
        self.assertEqual((t["teleports"], t["hops"], t["max_axis_move_m"], t["max_axis_cells"]), (5, 0, 150.0, 2))
        self.assertEqual(t["margin_s"], round(mk.runner_timeout(5) - mk.runner_seconds(5, 10000, 0)))
        self.assertGreaterEqual(t["margin_s"], mk.MIN_MARGIN_S)
        t = mk.entry_travel((0.0, 0.0), {"points": pts[:1] + [dict(pts[1], x=900.0)], "settle_ms": 10000, "hop_m": 200})
        self.assertEqual(t["hops"], 4)                                                  # 900 m in 5 teleports

    def test_waypoints_keep_every_leg_within_hop_m(self):
        w = local_world([], ground=3.0, origin=-100.0, size=1024)                      # flat, x and y -100 .. 699 m
        seq = [{"label": "far", "x": 500.0, "y": 0.0, "expect": 3.0}]
        pts, left = mk.add_waypoints(w, (0.0, 0.0, 3.0), seq, (0.0, 0.0), 300.0)
        self.assertEqual([p["label"] for p in pts], ["wp_01", "wp_02", "far"])        # 500 m: 2 waypoints at 185 m
        self.assertEqual(left, [])
        here = (0.0, 0.0)
        for p in pts:
            self.assertLessEqual(math.hypot(p["x"] - here[0], p["y"] - here[1]), mk.HOP_M)
            here = (p["x"], p["y"])
        self.assertTrue(all(p["kind"] == "terrain" and p["expect"] == 3.0 for p in pts[:2]))
        self.assertEqual(mk.entry_travel((0.0, 0.0), {"points": pts, "settle_ms": 9000, "hop_m": mk.HOP_M})["hops"], 0)
        # an object over the first ideal place: the waypoint moves to open terrain beside it, legs still within hop_m
        w = local_world([("SHED", (150.0, -12.0, 0.0, 185.0, 12.0, 6.0))], ground=3.0, origin=-100.0, size=1024)
        pts, left = mk.add_waypoints(w, (0.0, 0.0, 3.0), seq, (0.0, 0.0), 300.0)
        self.assertEqual(left, [])
        self.assertGreaterEqual(abs(pts[0]["y"]), 12.0 + 1.0)
        here = (0.0, 0.0)
        for p in pts:
            self.assertLessEqual(math.hypot(p["x"] - here[0], p["y"] - here[1]), mk.HOP_M)
            here = (p["x"], p["y"])
        # no open terrain anywhere near the leg: no waypoint, the runner hops it
        w = local_world([("BLOCK", (60.0, -60.0, 0.0, 440.0, 60.0, 6.0))], ground=3.0, origin=-100.0, size=1024)
        pts, left = mk.add_waypoints(w, (0.0, 0.0, 3.0), seq, (0.0, 0.0), 300.0)
        self.assertEqual([p["label"] for p in pts], ["far"])
        self.assertEqual(left[0]["to"], "far")

    def test_waypoint_ok_wants_moderate_relief(self):
        w = local_world([], ground=0.0, origin=-100.0, size=256)
        self.assertEqual(mk.waypoint_ok(w, 0.0, 0.0, 300.0), (0.0, 0.0))
        w.heights = np.tile(np.arange(256, dtype=np.float64) * tg.SF_STEP_M * 0.2, (256, 1))   # a 20 % grade in x
        self.assertIsNone(mk.waypoint_ok(w, 0.0, 0.0, 300.0))
        w.heights = np.tile(np.arange(256, dtype=np.float64) * tg.SF_STEP_M * 0.05, (256, 1))  # 5 %
        g, spread = mk.waypoint_ok(w, 0.0, 0.0, 300.0)
        self.assertAlmostEqual(g, 100.0 * 0.05, places=6)
        self.assertLess(spread, mk.WAYPOINT_MAX_SPREAD)

    def test_scenarios(self):
        w = local_world([("ROOF", (-5, 20, 0, 5, 30, 4.0))], ground=2.0)
        entry = {"z_ref": "zref_ground", "points": [{"label": "zref_ground", "x": 0.0, "y": 0.0, "expect": 2.0},
                                                     {"label": "roof", "x": 0.0, "y": 25.0, "expect": 4.0}]}
        meta = {"zref_ground": {"kind": "terrain_ref"}, "roof": {"kind": "object_top"}}
        self.assertEqual(mk.scenario_reads(w, entry, meta, "no_objects"), [2.0, 2.0])
        self.assertEqual(mk.scenario_reads(w, entry, meta, "flat_terrain"), [w.hmin, 4.0])
        entry["drop_z"] = 50.0
        entry["points"].append({"label": "edge", "x": 5.3, "y": 25.0, "expect": 2.0})  # terrain 0.3 m from the roof
        meta["edge"] = {"kind": "terrain_near_object"}
        self.assertEqual(mk.scenario_reads(w, entry, meta, "landing_max"), [2.0, 4.0, 4.0])


class CompoundTopTests(unittest.TestCase):
    """make_core64c.compound_top with a synthetic NIF and packfile (decoders patched): body placement as
    routes.collision_bodies (node translation in game units / 70, Havok units = metres), then the reference."""

    def run_top(self, position=(0.0, 0.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0), node_tr=(70.0, 0.0, 0.0), layer=1):
        from unittest import mock
        from fo4sf import ba2, fo4_compounds, hkpackfile, nif as nifmod
        blocks = [struct.pack("<iHiI", 1, 0, 2, 0), b"", struct.pack("<I", 4) + b"PACK"]
        types = ["bhkNPCollisionObject", "NiNode", "bhkPhysicsSystem"]
        fake_nif = type("F", (), {"blocks": blocks, "type_of": lambda self, i: types[i]})()
        leaf = {"points": [(-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, 1.0, 2.0), (-1.0, 1.0, 2.0)],
                "triangles": [(0, 1, 2), (0, 2, 3)]}

        class Pack:
            def __init__(self, blob):
                pass

            def objects(self):
                return [(10, "hknpPhysicsSystemData")]

            def array(self, at):
                return 100, 1

            def unpack(self, fmt, at):
                return (layer,)

        class Arc:
            def __init__(self, path):
                pass

            def find(self, name):
                return 0 if name == "meshes\\a\\b.nif" else None

            def read(self, name):
                return b"NIF"
        owner = {"model": "fo4core\\a\\b.nif", "pos": [10.0, 20.0, 5.0], "rot": [0.0, 0.0, 0.0], "scale": 2.0}
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "Fallout4 - Meshes.ba2"), "wb").close()
            with mock.patch.object(ba2, "Ba2", Arc), mock.patch.object(nifmod, "parse", return_value=fake_nif), \
                    mock.patch.object(nifmod, "world_transforms",
                                      return_value=lambda t: (node_tr, (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0)), \
                    mock.patch.object(fo4_compounds, "decode_body", return_value={
                        "position_havok_units": list(position), "quaternion_xyzw": list(quat), "leaves": [leaf]}), \
                    mock.patch.object(hkpackfile, "Packfile", Pack):
                return mk.compound_top(tmp, owner, 12.0, 20.0, 100.0)

    def test_top_placed_like_routes_then_the_reference(self):
        top, layer, rep = self.run_top()
        # leaf top z 2 m, node +1 m in x (70 units), reference scale 2 at z 5: the square spans x 10..14, top 9
        self.assertAlmostEqual(top, 9.0)
        self.assertEqual((layer, rep["bodies"], rep["leaves"], rep["skipped_body_transform"]), (1, 1, 1, 0))

    def test_body_with_its_own_transform_is_counted_not_placed(self):
        top, layer, rep = self.run_top(position=(0.5, 0.0, 0.0))
        self.assertIsNone(top)
        self.assertEqual(rep["skipped_body_transform"], 1)
        top, _layer, rep = self.run_top(quat=(0.0, 0.0, 0.7071, 0.7071))
        self.assertIsNone(top)


class StageTests(unittest.TestCase):
    def test_link_tree_and_archive_estimate(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "convert", "meshes", "fo4core")
            os.makedirs(src)
            with open(os.path.join(src, "a.nif"), "wb") as f:
                f.write(b"x" * 10)
            out = os.path.join(tmp, "out")
            self.assertEqual(mk.link_tree(os.path.join(tmp, "convert", "meshes"), os.path.join(out, "Data", "meshes")),
                             (1, 0, 0))
            self.assertTrue(os.path.samefile(os.path.join(src, "a.nif"), os.path.join(out, "Data", "meshes", "fo4core", "a.nif")))
            self.assertEqual(mk.link_tree(os.path.join(tmp, "convert", "meshes"), os.path.join(out, "Data", "meshes")),
                             (0, 0, 1))
            files = mk.data_files(out)
            self.assertEqual(files, [("meshes/fo4core/a.nif", 10)])
            self.assertEqual(mk.ba2_size(files), 32 + 36 + 10 + 2 + len("meshes/fo4core/a.nif"))

    def test_data_manifest_sees_an_in_place_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "convert", "textures")
            os.makedirs(src)
            with open(os.path.join(src, "a.dds"), "wb") as f:
                f.write(b"x" * 10)
            out = os.path.join(tmp, "out")
            mk.link_tree(os.path.join(tmp, "convert", "textures"), os.path.join(out, "Data", "textures"))
            with open(os.path.join(out, "P.esm"), "wb") as f:
                f.write(b"TES4")
            old = mk.data_manifest(out, ["P.esm"])
            self.assertEqual(sorted(old), ["Data/textures/a.dds", "P.esm"])
            os.replace(os.path.join(src, "a.dds"), os.path.join(src, "b.dds"))         # a new link there: unchanged
            self.assertEqual(mk.manifest_diff(old, mk.data_manifest(out, ["P.esm"])),
                             {"missing": [], "added": [], "changed": []})
            with open(os.path.join(src, "b.dds"), "wb") as f:                          # rewritten in place: changed
                f.write(b"y" * 12)
            self.assertEqual(mk.manifest_diff(old, mk.data_manifest(out, ["P.esm"]))["changed"], ["Data/textures/a.dds"])

    def test_terrain_edids(self):
        prm = {"overlays": [{"world": "W", "block": "WBlock", "location": "WLoc", "anchor": {"edid": "WAnchor"},
                             "coc": "Spawn"}]}
        self.assertEqual(mk.terrain_edids(prm), {"w", "wblock", "wloc", "wanchor", "spawn", "spawnmarker"})

    def test_abs_stats(self):
        s = mk.abs_stats([0.001, -0.002, 0.003, -0.5])
        self.assertEqual((s["count"], s["max_mm"], s["within_1cm"]), (4, 500.0, 3))
        s = mk.signed_stats([1.0, -2.0, 3.0])
        self.assertEqual((s["min"], s["median"], s["max"]), (-2.0, 1.0, 3.0))


class ContainerPerBaseTests(unittest.TestCase):
    def test_entries_of_one_base_share_the_cont_edid(self):
        bases = [{"edid": "FO4Core_x", "model": "m.nif", "source": "s.nif"}]
        placed = [{"src": "000001:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [0, 0, 0], "rot": [0, 0, 0], "scale": 1.0},
                  {"src": "000002:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [1, 0, 0], "rot": [0, 0, 0], "scale": 1.0},
                  {"src": "000003:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [2, 0, 0], "rot": [0, 0, 0], "scale": 1.0}]
        items = [{"form": "Starfield.esm:00000F", "count": 1}]
        cluster = {"containers": [{"src": "000001:Fallout4.esm", "name": "A", "items": items, "base": "04B6E9:Fallout4.esm"},
                                  {"src": "000002:Fallout4.esm", "name": "A", "items": items, "base": "04B6E9:Fallout4.esm"},
                                  {"src": "000003:Fallout4.esm", "name": "B", "items": items}]}
        keep, conts = mk.cluster_containers(bases, placed, cluster)
        self.assertEqual(keep, [])
        self.assertEqual([c["edid"] for c in conts], ["FO4Core_cont_04b6e9_fallout4", "FO4Core_cont_04b6e9_fallout4", "FO4Core_cont_000003"])
        self.assertEqual([c["reference_index"] for c in conts], [0, 1, 2])

    def test_the_plugin_is_part_of_the_group_and_metadata_must_agree(self):
        # Codex's review of #167: 04B6E9:Fallout4.esm and 04B6E9:SomeDLC.esm are two bases; one group, one name and inventory
        self.assertNotEqual(mk.container_edid("04B6E9:Fallout4.esm", "x"), mk.container_edid("04B6E9:SomeDLC.esm", "x"))
        self.assertEqual(mk.container_edid(None, "19EE52:Fallout4.esm"), "FO4Core_cont_19ee52")
        bases = [{"edid": "FO4Core_x", "model": "m.nif", "source": "s.nif"}]
        placed = [{"src": "000001:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [0, 0, 0], "rot": [0, 0, 0], "scale": 1.0},
                  {"src": "000002:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [1, 0, 0], "rot": [0, 0, 0], "scale": 1.0}]
        items = [{"form": "Starfield.esm:00000F", "count": 25}]
        same = {"containers": [{"src": "000001:Fallout4.esm", "name": "A", "items": items, "base": "04B6E9:Fallout4.esm"},
                               {"src": "000002:Fallout4.esm", "name": "A", "items": [{"form": "starfield.esm:00000F", "count": 25}], "base": "04B6E9:Fallout4.esm"}]}
        mk.cluster_containers(bases, placed, same)                 # the same inventory, case aside: shared
        for bad in ({"name": "B", "items": items}, {"name": "A", "items": [{"form": "Starfield.esm:00000F", "count": 99}]}):
            cl = {"containers": [{"src": "000001:Fallout4.esm", "name": "A", "items": items, "base": "04B6E9:Fallout4.esm"},
                                 dict(bad, src="000002:Fallout4.esm", base="04B6E9:Fallout4.esm")]}
            with self.assertRaises(ValueError) as cm:
                mk.cluster_containers(bases, placed, cl)
            self.assertIn("different name or inventory", str(cm.exception))

    def test_check_accepts_a_shared_cont_base(self):
        objects = {"refs": [], "containers": [{"src": "000001:Fallout4.esm", "reference_index": 0}, {"src": "000002:Fallout4.esm", "reference_index": 1}]}
        ids = {"bases": {"FO4Core_x": "000800"}, "refs": {},
               "containers": {"000001:Fallout4.esm": {"base": "000803", "ref": "000801"}, "000002:Fallout4.esm": {"base": "000803", "ref": "000802"}}}
        mk.check_reference_slots(objects, ids)                      # shared base 000803 after the two reserved slots: fine
        ids["containers"]["000002:Fallout4.esm"]["base"] = "000802"
        with self.assertRaises(ValueError):
            mk.check_reference_slots(objects, ids)                  # a base inside the reserved slots is not

class NavmeshInputTests(unittest.TestCase):
    OV = {"cell_min": -32, "cell_max": 31}

    def test_accepts_exp2d_shaped_input(self):
        nav = {"navmeshes": [{"cell": [-10, 11], "triangles": [[0, 1, 2]]}, {"cell": [31, -32], "triangles": [[0, 1, 2]]}]}
        self.assertIs(mk.navmesh_input(nav, self.OV), nav)

    def test_refuses_bad_input(self):
        for bad, why in (({}, "navmeshes"), ({"navmeshes": []}, "navmeshes"),
                         ({"navmeshes": [{"cell": [32, 0], "triangles": [[0, 1, 2]]}]}, "outside"),
                         ({"navmeshes": [{"cell": [0], "triangles": [[0, 1, 2]]}]}, "cell"),
                         ({"navmeshes": [{"cell": [0, 0], "triangles": []}]}, "triangles")):
            with self.assertRaises(ValueError, msg=why) as cm:
                mk.navmesh_input(bad, self.OV)
            self.assertIn(why, str(cm.exception))


class ItemPromotionTests(unittest.TestCase):
    """Loose items (commonwealth-build-plan.md section 3): --cluster "items" become native MISC references, one MISC per
    FO4 base, in the same slot plan as containers."""
    BASES = [{"edid": "FO4Core_cram", "model": "fo4core\\setdressing\\cram.nif"},
             {"edid": "FO4Core_cram_b", "model": "fo4core\\setdressing\\cram_b.nif"},
             {"edid": "FO4Core_kit", "model": "fo4core\\setdressing\\kit.nif"}]

    @staticmethod
    def placed(n=5, disabled=()):
        return [{"src": f"{i + 1:06X}:Fallout4.esm", "base": 0 if i != 4 else 1, "cell": [0, i], "pos": [1.0 + i, 2.0, 3.0],
                 "rot": [0, 0, 0.5], "scale": 1.0, "disabled": i in disabled} for i in range(n)]

    @staticmethod
    def item(i, **kw):
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "name": "Cram", "value": 7, "weight": 0.2, "base": "04B6E9:Fallout4.esm",
             "editor_id": "CramStack", "kind": "Ingestible", "slot": i}
        e.update(kw)
        return e

    def test_items_of_one_base_share_the_misc_and_carry_the_reference(self):
        cl = {"items": [self.item(1), self.item(3), self.item(2, base=None, name="Can")]}
        keep, items = mk.cluster_items(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], ["000001:Fallout4.esm", "000005:Fallout4.esm"])
        self.assertEqual([i["edid"] for i in items], ["FO4Core_misc_04b6e9_fallout4", "FO4Core_misc_000003",
                                                      "FO4Core_misc_04b6e9_fallout4"])
        self.assertEqual([i["reference_index"] for i in items], [1, 2, 3])
        it = items[0]
        self.assertEqual((it["src"], it["model"], it["name"], it["value"], it["weight"]),
                         ("000002:Fallout4.esm", self.BASES[0]["model"], "Cram", 7, 0.2))
        self.assertEqual((it["cell"], it["pos"], it["rot"], it["scale"]), ([0, 1], [2.0, 2.0, 3.0], [0, 0, 0.5], 1.0))
        self.assertEqual(mk.item_edid("04B6E9:Fallout4.esm", "x"), "FO4Core_misc_04b6e9_fallout4")
        self.assertNotEqual(mk.item_edid("04B6E9:Fallout4.esm", "x"), mk.item_edid("04B6E9:DLCCoast.esm", "x"))
        self.assertNotEqual(mk.item_edid("04B6E9:Fallout4.esm", "x"), mk.container_edid("04B6E9:Fallout4.esm", "x"))
        self.assertEqual(mk.cluster_items(self.BASES, self.placed(), {"containers": []}), (self.placed(), []))

    def test_entries_of_one_edid_must_agree(self):
        for bad, why in (({"name": "Cram (old)"}, "name"), ({"value": 8}, "value"), ({"weight": 0.25}, "weight")):
            with self.assertRaisesRegex(ValueError, "different name, value, weight or model", msg=why):
                mk.cluster_items(self.BASES, self.placed(), {"items": [self.item(1), self.item(3, **bad)]})
        # reference 000005 is placed with another converted model (base 1) under the same FO4 base: refused
        with self.assertRaisesRegex(ValueError, "different name, value, weight or model"):
            mk.cluster_items(self.BASES, self.placed(), {"items": [self.item(1), self.item(4)]})
        mk.cluster_items(self.BASES, self.placed(), {"items": [self.item(1), self.item(3, weight=0.2, value=7)]})

    def test_not_placed_disabled_and_malformed_entries_are_refused(self):
        with self.assertRaisesRegex(ValueError, "not placed"):
            mk.cluster_items(self.BASES, self.placed(), {"items": [self.item(1, src="ABCDEF:Fallout4.esm")]})
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_items(self.BASES, self.placed(disabled=(1,)), {"items": [self.item(1)]})
        with self.assertRaisesRegex(ValueError, "twice"):
            mk.cluster_items(self.BASES, self.placed(), {"items": [self.item(1), self.item(1)]})
        for bad, why in (({"name": None}, "name"), ({"name": " "}, "name"), ({"value": -1}, "value"),
                         ({"value": 1.5}, "value"), ({"value": True}, "value"), ({"weight": -0.1}, "weight"),
                         ({"weight": "0.2"}, "weight"), ({"weight": float("nan")}, "weight")):
            with self.assertRaisesRegex(ValueError, why):
                mk.cluster_items(self.BASES, self.placed(), {"items": [self.item(1, **bad)]})

    def test_containers_and_items_share_one_slot_plan(self):
        self.plan()

    def plan(self):
        """A mixed cluster (one container, two items of one FO4 base) and the identities the writer declares for it."""
        kit = {"src": "000003:Fallout4.esm", "name": "First Aid Kit", "items": [{"form": "Starfield.esm:00000F", "count": 25}],
               "base": "04B6E9:Fallout4.esm"}
        cl = {"containers": [kit], "items": [self.item(3), self.item(0)]}
        keep, promoted = mk.cluster_promote(self.BASES, self.placed(), cl)
        conts, items = promoted["containers"], promoted["items"]
        self.assertEqual((promoted["activators"], promoted["terminals"]), ([], []))
        self.assertEqual([p["src"] for p in keep], ["000002:Fallout4.esm", "000005:Fallout4.esm"])
        self.assertEqual([c["reference_index"] for c in conts], [2])
        self.assertEqual([i["reference_index"] for i in items], [0, 3])          # slots of the unpromoted list
        self.assertEqual(conts[0]["edid"], "FO4Core_cont_04b6e9_fallout4")
        self.assertEqual(items[0]["edid"], "FO4Core_misc_04b6e9_fallout4")
        with self.assertRaisesRegex(ValueError, "both a container and an item"):
            mk.cluster_promote(self.BASES, self.placed(), {"containers": [kit], "items": [self.item(2)]})
        # what the writer declares for that plan: bases 000800..000802, slots 000803..000807, then CONT, then MISC
        objects = {"refs": keep, "containers": conts, "items": items}
        ids = {"bases": {"a": "000800", "b": "000801", "c": "000802"},
               "refs": {"000002:Fallout4.esm": "000804", "000005:Fallout4.esm": "000807"},
               "containers": {"000003:Fallout4.esm": {"base": "000808", "ref": "000805"}},
               "items": {"000001:Fallout4.esm": {"base": "000809", "ref": "000803"},
                         "000004:Fallout4.esm": {"base": "000809", "ref": "000806"}}}
        mk.check_reference_slots(objects, ids)
        return objects, ids

    def test_slot_check_refuses_moved_overlapping_or_inconsistent_identities(self):
        objects, good = self.plan()
        cases = (
            ("moved", lambda i: i["items"]["000001:Fallout4.esm"].update(ref="000804") or i["refs"].update({"000002:Fallout4.esm": "000803"})),
            ("item base overlaps", lambda i: i["items"]["000004:Fallout4.esm"].update(base="000807")),
            ("other promoted class", lambda i: [v.update(base="000808") for v in i["items"].values()]),
            ("two bases", lambda i: i["items"]["000004:Fallout4.esm"].update(base="00080A")),
            ("differs from objects", lambda i: i.pop("items")),
        )
        for why, change in cases:
            ids = json.loads(json.dumps(good))
            change(ids)
            with self.assertRaisesRegex(ValueError, why):
                mk.check_reference_slots(objects, ids)
        two = json.loads(json.dumps(objects))
        two["items"][1]["edid"] = "FO4Core_misc_000004"                       # two edids, one declared base: refused
        with self.assertRaisesRegex(ValueError, "two edids"):
            mk.check_reference_slots(two, good)
        dup = json.loads(json.dumps(objects))
        dup["items"][1]["reference_index"] = 2                                 # the container's slot
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mk.check_reference_slots(dup, good)

    def test_check_counts_and_record_bindings(self):
        objects, ids = self.plan()
        own = 0x01000000

        def z(text):
            return text.encode("cp1252") + b"\0"

        def refr(fid, base, e):
            return {"sig": "REFR", "fid": own | fid, "flags": 0,
                    "fields": [(b"NAME", struct.pack("<I", own | base)), (b"DATA", struct.pack("<6f", *e["pos"], *e["rot"]))]}

        def misc(fid, e, value=None):
            return {"sig": "MISC", "fid": own | fid, "flags": 0,
                    "fields": [(b"EDID", z(e["edid"])), (b"MODL", z(e["model"])), (b"FULL", z(e["name"])),
                               (b"DATA", struct.pack("<if", e["value"] if value is None else value, e["weight"]))]}
        c, i0, i1 = objects["containers"][0], objects["items"][0], objects["items"][1]
        recs = [{"sig": "STAT", "fid": own | 0x800 + k, "flags": 0, "fields": []} for k in range(3)]
        recs += [{"sig": "REFR", "fid": own | 0x804, "flags": 0, "fields": []}, {"sig": "REFR", "fid": own | 0x807, "flags": 0, "fields": []},
                 refr(0x805, 0x808, c), refr(0x803, 0x809, i0), refr(0x806, 0x809, i1),
                 {"sig": "CONT", "fid": own | 0x808, "flags": 0, "fields": [(b"EDID", z(c["edid"])), (b"MODL", z(c["model"]))]},
                 misc(0x809, i0), {"sig": "REFR", "fid": own | 0x80A, "flags": 0, "fields": []},
                 {"sig": "REFR", "fid": own | 0x80B, "flags": 0, "fields": []}]            # COC marker, anchor
        exp = {"objects": {"exported": 7, "skipped": {"no model": 2}}}
        res = mk.promotion_checks(recs, own, objects, ids, exp)
        self.assertTrue(all(ok for _what, ok in res), res)
        self.assertEqual(len(res), 5)
        self.assertIn("1 MISC = 1 distinct items edids (2 items)", [w for w, _ok in res][3])
        bad = [dict(r) for r in recs]
        bad[bad.index(next(r for r in bad if r["sig"] == "MISC"))] = misc(0x809, i0, value=99)
        res = dict((w.split(" (")[0], ok) for w, ok in mk.promotion_checks(bad, own, objects, ids, exp))
        self.assertFalse(res["every promoted REFR names its CONT / MISC"])
        two = recs + [dict(misc(0x80C, i1), fid=own | 0x80C)]                             # a second MISC for one edid
        res = [ok for _w, ok in mk.promotion_checks(two, own, objects, ids, exp)]
        self.assertEqual(res[:4], [True, True, True, False])
        res = [ok for _w, ok in mk.promotion_checks(recs, own, objects, ids, {"objects": {"exported": 8, "skipped": {"no model": 2}}})]
        self.assertEqual(res[:2], [True, False])                                           # a reference lost in promotion
        res = [ok for _w, ok in mk.promotion_checks(recs[:-1], own, objects, ids, exp)]
        self.assertFalse(res[0])                                                           # one REFR short


class ItemValidationReviewTests(unittest.TestCase):
    # the review of #235: input the writer refuses is refused at stage (value int32, weight float32, -0.0 == 0.0)
    def _two(self, **first):
        bases = [{"edid": "FO4Core_x", "model": "m.nif", "source": "s.nif"}]
        placed = [{"src": f"00000{i}:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [i, 0, 0], "rot": [0, 0, 0], "scale": 1.0}
                  for i in (1, 2)]
        entries = [dict({"src": "000001:Fallout4.esm", "name": "A", "value": 1, "weight": 0.0, "base": "000AAA:Fallout4.esm"}, **first),
                   {"src": "000002:Fallout4.esm", "name": "A", "value": 1, "weight": -0.0, "base": "000AAA:Fallout4.esm"}]
        return mk.cluster_items(bases, placed, {"items": entries})

    def test_zero_and_negative_zero_weight_share_one_record(self):
        keep, items = self._two()
        self.assertEqual(len({i["edid"] for i in items}), 1)                 # shared, not refused

    def test_out_of_range_value_and_weight_are_refused(self):
        for bad in ({"value": 2 ** 31}, {"value": -1}, {"weight": 1e39}):
            with self.assertRaises(ValueError, msg=str(bad)):
                self._two(**bad)


class ScriptedDoorTests(unittest.TestCase):
    """Scripted load doors (docs/terrain/scripted-doors.md): --cluster "doors" keeps the REFR slot, one ACTI per FO4 door
    base, the FO4SF_LoadDoor VMAD with the interior destination, an arrival XMarker with a new id."""
    BASES = [{"edid": "FO4Core_indmetaldoorload01", "model": "fo4core\\interiors\\industrial\\doors\\indmetaldoorload01.nif"},
             {"edid": "FO4Core_cram", "model": "fo4core\\setdressing\\foodandfoodware\\cram.nif"}]
    OBND = [[-0.6857, -0.0554, 0.0141], [0.6859, 0.0559, 2.4002]]

    def placed(self):
        return [{"src": "0EE661:Fallout4.esm", "base": 0, "cell": [-5, 6], "pos": [-469.8529, 636.70886, 42.35599], "rot": [0, 0, 2.5812104], "scale": 1.0, "disabled": False},
                {"src": "152DA0:Fallout4.esm", "base": 1, "cell": [-10, 11], "pos": [-999.31, 1142.45, 105.76], "rot": [0, 0, 0], "scale": 1.0, "disabled": False},
                {"src": "130DEC:Fallout4.esm", "base": 0, "cell": [-13, -1], "pos": [-1265.3715, -74.9713, 80.4571], "rot": [0, 0, 1.5708], "scale": 1.0, "disabled": False},
                {"src": "000001:Fallout4.esm", "base": 0, "cell": [-10, 12], "pos": [-990, 1201, 105], "rot": [0, 0, 0], "scale": 1.0, "disabled": True}]

    def door(self, src="0EE661:Fallout4.esm", **kw):
        e = {"src": src, "base": "018C8B:Fallout4.esm", "name": "Door", "obnd": [[-0.8, -0.22857, 0.0], [0.8, 0.11429, 2.51429]],
             "destination": {"plugin": "FO4Port.esm", "port_id": 32011, "door": "0EE5D6:Fallout4.esm", "cell": "SuperDuperMart01"},
             "arrival_out": {"pos": [-469.44414, 636.07411, 42.35599], "rot": [0, 0, 2.5812104]}}
        e.update(kw)
        return e

    def test_contract_matches_the_papyrus_script(self):
        src = (root / "scripts" / "door_bridge" / "FO4SF_LoadDoor.psc").read_text(encoding="utf-8")
        self.assertRegex(src, rf"(?m)^Scriptname {mk.DOOR_SCRIPT} extends ObjectReference")
        self.assertRegex(src, rf"(?m)^string Property {mk.DOOR_PLUGIN_PROPERTY} Auto")
        self.assertRegex(src, rf"(?m)^int Property {mk.DOOR_ID_PROPERTY} Auto")

    def test_door_keeps_slot_and_carries_script_arrival_and_bounds(self):
        bounds = {"fo4core\\interiors\\industrial\\doors\\indmetaldoorload01.nif": self.OBND}
        keep, doors = mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.door()]}, cells=(-32, 31), bounds_of=bounds.get)
        self.assertEqual([p["src"] for p in keep], ["152DA0:Fallout4.esm", "130DEC:Fallout4.esm", "000001:Fallout4.esm"])
        d = doors[0]
        self.assertEqual((d["src"], d["edid"], d["reference_index"], d["name"]), ("0EE661:Fallout4.esm", "FO4Core_door_018c8b_fallout4", 0, "Door"))
        self.assertEqual(d["model"], self.BASES[0]["model"])
        self.assertEqual(d["obnd"], self.OBND)                                         # the converted mesh's collision
        self.assertEqual(d["script"], {"name": "FO4SF_LoadDoor", "properties": {"DestinationPlugin": "FO4Port.esm", "DestinationId": 32011}})
        self.assertEqual(d["destination"], {"plugin": "FO4Port.esm", "id": 32011, "door": "0EE5D6:Fallout4.esm", "cell": "SuperDuperMart01"})
        self.assertEqual(d["arrival"], {"pos": [-469.44414, 636.07411, 42.35599], "rot": [0, 0, 2.5812104], "cell": [-5, 6]})
        self.assertEqual((d["cell"], d["pos"], d["rot"], d["scale"], d["rigged"]), ([-5, 6], [-469.8529, 636.70886, 42.35599], [0, 0, 2.5812104], 1.0, False))
        # without collision bounds the FO4 base's bounds serve; two doors of one base share the ACTI
        second = self.door("130DEC:Fallout4.esm", arrival_out={"pos": [-1264.123, -75.04758, 80.45714], "rot": [0, 0, 1.5708]},
                           destination={"plugin": "FO4Port.esm", "port_id": 51113})
        _keep, two = mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.door(), second]}, cells=(-32, 31), bounds_of=lambda m: None)
        self.assertEqual([t["edid"] for t in two], ["FO4Core_door_018c8b_fallout4"] * 2)
        self.assertEqual(two[0]["obnd"], [[-0.8, -0.22857, 0.0], [0.8, 0.11429, 2.51429]])
        self.assertEqual([t["reference_index"] for t in two], [0, 2])

    def test_refusals(self):
        cases = (
            ("not placed", {"doors": [self.door("ABCDEF:Fallout4.esm")]}),                   # a missing side has no slot
            ("not placed", {"doors": [self.door("08EB65:Fallout4.esm")]}),                   # the cave's editor marker
            ("listed twice", {"doors": [self.door(), self.door()]}),
            ("disabled", {"doors": [self.door("000001:Fallout4.esm")]}),
            ("plugin-local id", {"doors": [self.door(destination={"plugin": "FO4Port.esm", "port_id": 0})]}),
            ("plugin-local id", {"doors": [self.door(destination={"plugin": "FO4Port.esm", "port_id": "7D0B"})]}),
            ("plugin-local id", {"doors": [self.door(destination={"plugin": "FO4Port.esm", "port_id": 0x1000000})]}),
            ("plugin file name", {"doors": [self.door(destination={"plugin": "FO4Port", "port_id": 1})]}),
            ("arrival", {"doors": [self.door(arrival_out=None)]}),
            ("arrival", {"doors": [self.door(arrival_out={"pos": [1, 2], "rot": [0, 0, 0]})]}),
            ("outside", {"doors": [self.door(arrival_out={"pos": [9000, 0, 0], "rot": [0, 0, 0]})]}),
            ("name", {"doors": [self.door(name="two\nlines")]}),
            ("bounds", {"doors": [self.door(obnd=None)]}),
            ("bounds", {"doors": [self.door(obnd=[[1, 0, 0], [0, 0, 0]])]}),
            ("different model, name or bounds", {"doors": [self.door(), self.door("130DEC:Fallout4.esm", name="Hatch")]}),
        )
        for why, cl in cases:
            with self.assertRaisesRegex(ValueError, why, msg=why):
                mk.cluster_doors(self.BASES, self.placed(), cl, cells=(-32, 31), bounds_of=lambda m: None)
        with self.assertRaisesRegex(ValueError, "both a container and a door"):
            mk.cluster_promote(self.BASES, self.placed(), {"containers": [{"src": "0EE661:Fallout4.esm", "name": "x", "items": [{"form": "Starfield.esm:00000F", "count": 1}]}], "doors": [self.door()]}, bounds_of=lambda m: None)
        self.assertEqual(mk.cluster_doors(self.BASES, self.placed(), {}), (self.placed(), []))

    def test_merge_clusters(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.json"), os.path.join(d, "b.json")
            json.dump({"note": "a", "containers": [{"src": "1"}], "items": []}, open(a, "w"))
            json.dump({"note": "b", "doors": [{"src": "2"}]}, open(b, "w"))
            self.assertEqual(mk.merge_clusters([a, b]), {"containers": [{"src": "1"}], "items": [], "doors": [{"src": "2"}]})
            json.dump({"containers": [{"src": "3"}]}, open(b, "w"))
            with self.assertRaisesRegex(ValueError, "containers listed in both"):
                mk.merge_clusters([a, b])

    def plan(self):
        """A door in slot 0 with a container in slot 1 and the identities the writer declares (bases 000800..000801, slots
        000802..000805, CONT 000806, NAVM 000807..000808, then the ACTI 000809 and the arrival marker 00080A)."""
        bounds = {"fo4core\\interiors\\industrial\\doors\\indmetaldoorload01.nif": self.OBND}
        kit = {"src": "152DA0:Fallout4.esm", "name": "Cram", "items": [{"form": "Starfield.esm:00000F", "count": 1}], "base": "0001:Fallout4.esm"}
        keep, promoted = mk.cluster_promote(self.BASES, self.placed(), {"containers": [kit], "doors": [self.door()]}, cells=(-32, 31), bounds_of=bounds.get)
        conts, items, doors = (promoted[k] for k in ("containers", "items", "doors"))
        objects = {"refs": keep, "containers": conts, "items": items, "doors": doors}
        ids = {"bases": {"a": "000800", "b": "000801"},
               "refs": {"130DEC:Fallout4.esm": "000804", "000001:Fallout4.esm": "000805"},
               "containers": {"152DA0:Fallout4.esm": {"base": "000806", "ref": "000803"}},
               "navmeshes": ["000807", "000808"],
               "doors": {"0EE661:Fallout4.esm": {"base": "000809", "ref": "000802", "arrival": "00080A"}}}
        mk.check_reference_slots(objects, ids)
        mk.check_door_identities(objects, ids)
        return objects, ids

    def test_door_identities(self):
        objects, good = self.plan()
        cases = (
            ("moved", lambda i: i["doors"]["0EE661:Fallout4.esm"].update(ref="000803") or i["containers"]["152DA0:Fallout4.esm"].update(ref="000802")),
            ("not after every other record", lambda i: i["doors"]["0EE661:Fallout4.esm"].update(base="000807")),
            ("not new id", lambda i: i["doors"]["0EE661:Fallout4.esm"].update(arrival="00080B")),
            ("differs from objects", lambda i: i["doors"].update({"130DEC:Fallout4.esm": {"base": "000809", "ref": "000804", "arrival": "00080B"}})),
            ("doors", lambda i: i.pop("doors")),
        )
        for why, change in cases:
            bad = copy.deepcopy(good)
            change(bad)
            with self.assertRaisesRegex(ValueError, why, msg=why):
                mk.check_reference_slots(objects, bad)
                mk.check_door_identities(objects, bad)

    def records(self, objects, ids, own=1 << 24):
        """Raw-walk-shaped records of the plan: the ACTI, the door REFR with its VMAD, the arrival marker, the CONT + REFR."""
        import vmad_patch
        d = objects["doors"][0]
        f = lambda *xs: list(xs)
        vmad = vmad_patch.load_door_vmad(mk.DOOR_SCRIPT, mk.DOOR_PLUGIN_PROPERTY, "FO4Port.esm", mk.DOOR_ID_PROPERTY, 32011)
        acti = {"sig": "ACTI", "fid": own | 0x809, "flags": 0, "fields": f((b"EDID", d["edid"].encode() + b"\0"), (b"OBND", struct.pack("<6f", *d["obnd"][0], *d["obnd"][1])),
                 (b"FULL", b"Door\0"), (b"MODL", d["model"].encode() + b"\0"), (b"PNAM", bytes.fromhex("cc4c3300")), (b"FNAM", b"\0\0"), (b"JNAM", struct.pack("<H", 360)))}
        ref = {"sig": "REFR", "fid": own | 0x802, "flags": 0, "fields": f((b"VMAD", vmad), (b"NAME", struct.pack("<I", own | 0x809)), (b"DATA", struct.pack("<6f", *d["pos"], *d["rot"])))}
        mark = {"sig": "REFR", "fid": own | 0x80A, "flags": 0, "fields": f((b"NAME", struct.pack("<I", 0x3B)), (b"DATA", struct.pack("<6f", *d["arrival"]["pos"], *d["arrival"]["rot"])))}
        c = objects["containers"][0]
        cont = {"sig": "CONT", "fid": own | 0x806, "flags": 0, "fields": f((b"EDID", c["edid"].encode() + b"\0"), (b"MODL", c["model"].encode() + b"\0"))}
        cref = {"sig": "REFR", "fid": own | 0x803, "flags": 0, "fields": f((b"NAME", struct.pack("<I", own | 0x806)), (b"DATA", struct.pack("<6f", *c["pos"], *c["rot"])))}
        others = [{"sig": "REFR", "fid": own | int(v, 16), "flags": 0, "fields": f((b"NAME", struct.pack("<I", own | 0x800)), (b"DATA", bytes(24)))} for v in ids["refs"].values()]
        return [acti, ref, mark, cont, cref] + others + [{"sig": "REFR", "fid": own | 0x7FF, "flags": 0, "fields": []}] * 2

    def test_door_record_check_and_counts(self):
        import vmad_patch
        objects, ids = self.plan()
        recs = self.records(objects, ids)
        self.assertEqual(mk.door_record_check(recs, 1 << 24, objects, ids), [])
        self.assertEqual(mk.promoted_record_check(recs, 1 << 24, objects, ids), [])
        exp = {"objects": {"exported": 6, "skipped": {"no_model": 2}}}
        res = mk.promotion_checks(recs, 1 << 24, objects, ids, exp)
        self.assertTrue(all(ok for _w, ok in res), res)
        self.assertTrue(any("1 ACTI = 1 distinct doors" in w for w, _ok in res))

        # and it notices: a wrong destination id, a missing VMAD, a persistent REFR, a wrong marker base, a wrong name
        def problems(change):
            bad = copy.deepcopy(recs)
            change(bad)
            return mk.door_record_check(bad, 1 << 24, objects, ids)
        other = vmad_patch.load_door_vmad(mk.DOOR_SCRIPT, mk.DOOR_PLUGIN_PROPERTY, "FO4Port.esm", mk.DOOR_ID_PROPERTY, 32012)
        self.assertTrue(any("VMAD properties" in p for p in problems(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", other)))))
        self.assertTrue(any("no VMAD" in p for p in problems(lambda r: r[1]["fields"].pop(0))))
        self.assertTrue(any("persistent" in p for p in problems(lambda r: r[1].update(flags=0x400))))
        self.assertTrue(any("XMarker" in p for p in problems(lambda r: r[2]["fields"].__setitem__(0, (b"NAME", struct.pack("<I", 0x32))))))
        self.assertTrue(any("ACTI name" in p for p in problems(lambda r: r[0]["fields"].__setitem__(2, (b"FULL", b"Hatch\0")))))
        self.assertTrue(any("JNAM" in p for p in problems(lambda r: r[0]["fields"].__setitem__(6, (b"JNAM", struct.pack("<H", 90))))))
        self.assertTrue(any("belongs to the REFR" in p for p in problems(lambda r: r[0]["fields"].append((b"VMAD", other)))))

if __name__ == "__main__":
    unittest.main()


class ClusterTests(unittest.TestCase):
    """R05: --cluster turns named placed references into native containers for TerrainOverlays."""
    BASES = [{"edid": "FO4Core_firstaidkitwhite", "model": "fo4core\setdressing\firstaidkit\firstaidkitwhite.nif"},
             {"edid": "FO4Core_cram", "model": "fo4core\setdressing\foodandfoodware\cram.nif"}]
    PLACED = [{"src": "19EE52:Fallout4.esm", "base": 0, "cell": [-10, 11], "pos": [-993.14, 1151.66, 105.3], "rot": [0, 0, 1.2], "scale": 1.0, "disabled": False},
              {"src": "152DA0:Fallout4.esm", "base": 1, "cell": [-10, 11], "pos": [-999.31, 1142.45, 105.76], "rot": [0, 0, 0], "scale": 1.0, "disabled": False},
              {"src": "000001:Fallout4.esm", "base": 1, "cell": [-10, 12], "pos": [-990, 1201, 105], "rot": [0, 0, 0], "scale": 1.0, "disabled": True}]
    CLUSTER = {"containers": [{"src": "19EE52:Fallout4.esm", "name": "First Aid Kit",
                               "items": [{"form": "Starfield.esm:00000F", "count": 25}, {"form": "Starfield.esm:00000A", "count": 1}]}]}

    def test_named_reference_becomes_a_container_and_leaves_the_statics(self):
        placed, conts = mk.cluster_containers(self.BASES, [dict(p) for p in self.PLACED], self.CLUSTER)
        self.assertEqual([p["src"] for p in placed], ["152DA0:Fallout4.esm", "000001:Fallout4.esm"])
        self.assertEqual(len(conts), 1)
        c = conts[0]
        self.assertEqual((c["src"], c["edid"], c["name"]), ("19EE52:Fallout4.esm", "FO4Core_cont_19ee52", "First Aid Kit"))
        self.assertEqual(c["model"], self.BASES[0]["model"])
        self.assertEqual(c["reference_index"], 0)
        self.assertEqual((c["cell"], c["pos"], c["rot"], c["scale"]), ([-10, 11], [-993.14, 1151.66, 105.3], [0, 0, 1.2], 1.0))
        self.assertEqual(c["items"][0], {"form": "Starfield.esm:00000F", "count": 25})

    def test_unplaced_disabled_or_malformed_entries_are_errors(self):
        with self.assertRaisesRegex(ValueError, "not placed"):
            mk.cluster_containers(self.BASES, [dict(p) for p in self.PLACED], {"containers": [dict(self.CLUSTER["containers"][0], src="ABCDEF:Fallout4.esm")]})
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_containers(self.BASES, [dict(p) for p in self.PLACED], {"containers": [dict(self.CLUSTER["containers"][0], src="000001:Fallout4.esm")]})
        with self.assertRaisesRegex(ValueError, "items"):
            mk.cluster_containers(self.BASES, [dict(p) for p in self.PLACED], {"containers": [dict(self.CLUSTER["containers"][0], items=[])]})
        with self.assertRaisesRegex(ValueError, "6 hex"):
            mk.cluster_containers(self.BASES, [dict(p) for p in self.PLACED], {"containers": [dict(self.CLUSTER["containers"][0], items=[{"form": "Credits", "count": 1}])]})

    def test_no_cluster_changes_nothing(self):
        placed, conts = mk.cluster_containers(self.BASES, [dict(p) for p in self.PLACED], {})
        self.assertEqual(len(placed), 3)
        self.assertEqual(conts, [])

    def test_original_indices_survive_removal_of_multiple_references(self):
        placed = [dict(p) for p in self.PLACED]
        placed[-1]["disabled"] = False
        cluster = {"containers": [self.CLUSTER["containers"][0],
                    dict(self.CLUSTER["containers"][0], src=placed[-1]["src"])]}
        kept, conts = mk.cluster_containers(self.BASES, placed, cluster)
        self.assertEqual([c["reference_index"] for c in conts], [0, 2])
        objects = {"refs": kept, "containers": conts}
        ids = {"bases": {"base0": "000900", "base1": "000901"},
               "refs": {kept[0]["src"]: "000903"},
               "containers": {conts[0]["src"]: {"base": "000905", "ref": "000902"},
                              conts[1]["src"]: {"base": "000906", "ref": "000904"}}}
        mk.check_reference_slots(objects, ids)
        ids["refs"][kept[0]["src"]] = "000902"  # old allocation reused the removed source's slot
        with self.assertRaisesRegex(ValueError, "moved"):
            mk.check_reference_slots(objects, ids)


class ActivatorTerminalPromotionTests(unittest.TestCase):
    """Activators and terminals (commonwealth-build-plan.md section 3): --cluster "activators" become native ACTI and
    "terminals" native TERM references with their own TMLM menu, one base per FO4 base, in the one slot plan."""
    BASES = [{"edid": "FO4Core_bell", "model": "fo4core\\setdressing\\boats\\bell_01.nif"},
             {"edid": "FO4Core_terminalon", "model": "fo4core\\furniture\\terminals\\terminalon.nif"},
             {"edid": "FO4Core_bell_b", "model": "fo4core\\setdressing\\boats\\bell_b.nif"}]
    BODY = "FO4 terminal (text not ported yet)"

    @staticmethod
    def placed(n=7, disabled=()):
        base = {4: 1, 5: 1, 6: 2}
        return [{"src": f"{i + 1:06X}:Fallout4.esm", "base": base.get(i, 0), "cell": [0, i], "pos": [1.0 + i, 2.0, 3.0],
                 "rot": [0, 0, 0.5], "scale": 1.0, "disabled": i in disabled} for i in range(n)]

    @staticmethod
    def acti(i, **kw):
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "name": "Bell", "base": "0BB1E1:Fallout4.esm", "editor_id": "Bell_Free"}
        e.update(kw)
        return e

    @classmethod
    def term(cls, i, **kw):
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "name": "Terminal", "body": cls.BODY, "base": "0E1E33:Fallout4.esm",
             "editor_id": "DefaultTerminalDesk"}
        e.update(kw)
        return e

    def test_body_constant_matches_make_cluster(self):
        import make_cluster as mc
        self.assertEqual(mk.TERMINAL_BODY, mc.TERMINAL_BODY)
        self.assertEqual(mk.TERMINAL_BODY, self.BODY)

    def test_activators_of_one_base_share_the_acti_and_carry_the_reference(self):
        cl = {"activators": [self.acti(1), self.acti(3), self.acti(2, base="0BB1E2:Fallout4.esm", name=None)]}
        keep, out = mk.cluster_activators(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], [f"{i:06X}:Fallout4.esm" for i in (1, 5, 6, 7)])
        self.assertEqual([e["edid"] for e in out], ["FO4Core_acti_0bb1e1_fallout4", "FO4Core_acti_0bb1e2_fallout4",
                                                    "FO4Core_acti_0bb1e1_fallout4"])
        self.assertEqual([e["reference_index"] for e in out], [1, 2, 3])
        self.assertEqual([e["name"] for e in out], ["Bell", None, "Bell"])                  # None: no FULL
        e = out[0]
        self.assertEqual((e["model"], e["cell"], e["pos"], e["rot"], e["scale"]),
                         (self.BASES[0]["model"], [0, 1], [2.0, 2.0, 3.0], [0, 0, 0.5], 1.0))
        self.assertEqual(mk.activator_edid(None, "19EE52:Fallout4.esm"), "FO4Core_acti_19ee52")
        self.assertEqual(mk.cluster_activators(self.BASES, self.placed(), {}), (self.placed(), []))

    def test_terminals_get_a_menu_edid_and_the_body(self):
        keep, out = mk.cluster_terminals(self.BASES, self.placed(), {"terminals": [self.term(5), self.term(4)]})
        self.assertEqual(len(keep), 5)
        self.assertEqual([(e["edid"], e["menu_edid"], e["reference_index"]) for e in out],
                         [("FO4Core_term_0e1e33_fallout4", "FO4Core_tmlm_0e1e33_fallout4", 4),
                          ("FO4Core_term_0e1e33_fallout4", "FO4Core_tmlm_0e1e33_fallout4", 5)])
        self.assertEqual((out[0]["name"], out[0]["body"], out[0]["model"]), ("Terminal", self.BODY, self.BASES[1]["model"]))
        no_body = self.term(4)
        del no_body["body"]                                                     # the default body line
        self.assertEqual(mk.cluster_terminals(self.BASES, self.placed(), {"terminals": [no_body]})[1][0]["body"], self.BODY)
        with self.assertRaisesRegex(ValueError, "not a terminal edid"):
            mk.terminal_menu_edid("FO4Core_acti_0e1e33_fallout4")

    def test_bad_entries_are_refused(self):
        P = self.placed()
        cases = (
            (mk.cluster_activators, {"activators": [self.acti(1), self.acti(3, name="Gong")]}, "different name / model"),
            (mk.cluster_activators, {"activators": [self.acti(1), self.acti(6)]}, "different name / model"),   # another model
            (mk.cluster_activators, {"activators": [self.acti(1, name="")]}, "neither none nor one line"),
            (mk.cluster_activators, {"activators": [self.acti(1, name="a\nb")]}, "neither none nor one line"),
            (mk.cluster_activators, {"activators": [self.acti(1), self.acti(1)]}, "twice"),
            (mk.cluster_activators, {"activators": [self.acti(1, src="ABCDEF:Fallout4.esm")]}, "not placed"),
            (mk.cluster_terminals, {"terminals": [self.term(4, name=None)]}, "name"),
            (mk.cluster_terminals, {"terminals": [self.term(4, body="line one\r\nline two")]}, "body"),
            (mk.cluster_terminals, {"terminals": [self.term(4, body=" ")]}, "body"),
            (mk.cluster_terminals, {"terminals": [self.term(4), self.term(5, body="other")]}, "different name / model / body"),
        )
        for fn, cl, why in cases:
            with self.assertRaisesRegex(ValueError, why, msg=cl):
                fn(self.BASES, P, cl)
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_terminals(self.BASES, self.placed(disabled=(4,)), {"terminals": [self.term(4)]})

    def plan(self):
        """A cluster of every class (a container, an item, two activators of one base, two terminals of one base) and
        the identities the writer declares for it: bases 800..802, slots 803..809, then CONT, MISC, ACTI, TERM, TMLM."""
        kit = {"src": "000007:Fallout4.esm", "name": "First Aid Kit", "items": [{"form": "Starfield.esm:00000F", "count": 25}],
               "base": "04B6E9:Fallout4.esm"}
        can = {"src": "000001:Fallout4.esm", "name": "Can", "value": 1, "weight": 0.1, "base": "059B02:Fallout4.esm"}
        cl = {"containers": [kit], "items": [can], "activators": [self.acti(3), self.acti(1)],
              "terminals": [self.term(4), self.term(5)]}
        keep, promoted = mk.cluster_promote(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], ["000003:Fallout4.esm"])
        self.assertEqual({k: [e["reference_index"] for e in v] for k, v in promoted.items()},
                         {"containers": [6], "items": [0], "activators": [1, 3], "terminals": [4, 5], "doors": []})
        objects = dict({"refs": keep}, **promoted)
        ids = {"bases": {"a": "000800", "b": "000801", "c": "000802"}, "refs": {"000003:Fallout4.esm": "000805"},
               "containers": {"000007:Fallout4.esm": {"base": "00080A", "ref": "000809"}},
               "items": {"000001:Fallout4.esm": {"base": "00080B", "ref": "000803"}},
               "activators": {"000002:Fallout4.esm": {"base": "00080C", "ref": "000804"},
                              "000004:Fallout4.esm": {"base": "00080C", "ref": "000806"}},
               "terminals": {"000005:Fallout4.esm": {"base": "00080D", "ref": "000807", "menu": "00080E"},
                             "000006:Fallout4.esm": {"base": "00080D", "ref": "000808", "menu": "00080E"}}}
        mk.check_reference_slots(objects, ids)
        return cl, objects, ids

    def test_every_class_shares_one_slot_plan(self):
        cl, _objects, _ids = self.plan()
        for k, other in (("items", "activators"), ("containers", "terminals")):
            two = json.loads(json.dumps(cl))
            two[other].append(dict(two[k][0], **({"name": "X", "body": self.BODY} if other == "terminals" else {})))
            with self.assertRaisesRegex(ValueError, "listed as both an? \\w+ and an? \\w+"):
                mk.cluster_promote(self.BASES, self.placed(), two)

    def test_an_edid_standing_for_two_fo4_sources_is_refused(self):
        # promoted_edid strips the plugin's punctuation and extension: A-B.esm and AB.esp both give FO4Core_acti_0bb1e1_ab
        cl = {"activators": [self.acti(1, base="0BB1E1:A-B.esm"), self.acti(3, base="0BB1E1:AB.esp")]}
        with self.assertRaisesRegex(ValueError, "two FO4 sources"):
            mk.cluster_promote(self.BASES, self.placed(), cl)
        cl = {"activators": [self.acti(1, base="0BB1E1:AB.esm"), self.acti(3, base="0bb1e1:ab.ESM")]}   # ASCII case: one
        self.assertEqual(len({e["edid"] for e in mk.cluster_promote(self.BASES, self.placed(), cl)[1]["activators"]}), 1)

    def test_slot_check_refuses_bad_menus_and_overlaps(self):
        _cl, objects, good = self.plan()
        T5, T6 = "000005:Fallout4.esm", "000006:Fallout4.esm"
        cases = (
            ("terminal menu overlaps", lambda i: [v.update(menu="000808") for v in i["terminals"].values()]),
            ("also a promoted base", lambda i: [v.update(menu="00080C") for v in i["terminals"].values()]),
            ("two menus", lambda i: i["terminals"][T6].update(menu="00080F")),
            ("activator base overlaps", lambda i: [v.update(base="000804") for v in i["activators"].values()]),
            ("another promoted class", lambda i: [v.update(base="00080B") for v in i["activators"].values()]),
            ("moved", lambda i: i["terminals"][T5].update(ref="000808") or i["terminals"][T6].update(ref="000807")),
            ("differs from objects", lambda i: i.pop("activators")),
            ("missing or invalid", lambda i: i["terminals"][T5].pop("menu")),
        )
        for why, change in cases:
            ids = json.loads(json.dumps(good))
            change(ids)
            with self.assertRaisesRegex(ValueError, why):
                mk.check_reference_slots(objects, ids)
        two = json.loads(json.dumps(objects))                          # two terminal edids, one declared menu
        two["terminals"][1]["edid"] = "FO4Core_term_0e1e34_fallout4"
        ids = json.loads(json.dumps(good))
        ids["terminals"][T6]["base"] = "00080F"
        with self.assertRaisesRegex(ValueError, "one menu declared for two terminal edids"):
            mk.check_reference_slots(two, ids)

    def records(self, objects, ids, own=0x01000000, **override):
        """Raw records the writer would give for plan(): the four STAT-side records only matter for the counts."""
        def z(text):
            return text.encode("utf-8") + b"\0"

        def refr(e, v):
            return {"sig": "REFR", "fid": own | int(v["ref"], 16), "flags": 0,
                    "fields": [(b"NAME", struct.pack("<I", own | int(v["base"], 16))),
                               (b"DATA", struct.pack("<6f", *e["pos"], *e["rot"]))]}
        recs = [{"sig": "REFR", "fid": own | 0x805, "flags": 0, "fields": []}]
        c = objects["containers"][0]
        recs.append({"sig": "CONT", "fid": own | 0x80A, "flags": 0, "fields": [(b"EDID", z(c["edid"])), (b"MODL", z(c["model"]))]})
        i = objects["items"][0]
        recs.append({"sig": "MISC", "fid": own | 0x80B, "flags": 0, "fields": [
            (b"EDID", z(i["edid"])), (b"MODL", z(i["model"])), (b"FULL", z(i["name"])), (b"DATA", struct.pack("<if", 1, 0.1))]})
        a = objects["activators"][0]
        recs.append({"sig": "ACTI", "fid": own | 0x80C, "flags": 0, "fields": [
            (b"EDID", z(a["edid"])), (b"MODL", z(a["model"])), (b"FULL", z(override.get("acti_name", a["name"])))]})
        t = objects["terminals"][0]
        recs.append({"sig": "TERM", "fid": own | 0x80D, "flags": 0, "fields": [
            (b"EDID", z(t["edid"])), (b"DNAM", struct.pack("<I", own | override.get("menu", 0x80E))), (b"NAM1", b"\x02"),
            (b"FULL", z(t["name"])), (b"MODL", z(t["model"]))]})
        recs.append({"sig": "TMLM", "fid": own | 0x80E, "flags": 0, "fields": [
            (b"EDID", z(t["menu_edid"])), (b"FULL", z(t["name"])), (b"TMVT", struct.pack("<I", 1)), (b"BSIZ", struct.pack("<I", 1))]
            + [(b"BTXT", z(b)) for b in override.get("bodies", [t["body"]])]
            + [(b"TPLT", b"\0"), (b"ISIZ", struct.pack("<I", override.get("isiz", 0)))]})
        for k in ("containers", "items", "activators", "terminals"):
            for e in objects[k]:
                recs.append(refr(e, ids[k][e["src"]]))
        recs += [{"sig": "REFR", "fid": own | 0x810, "flags": 0, "fields": []},
                 {"sig": "REFR", "fid": own | 0x811, "flags": 0, "fields": []}]                # COC marker, anchor
        return recs

    def test_check_counts_and_bindings_of_every_class(self):
        _cl, objects, ids = self.plan()
        own, exp = 0x01000000, {"objects": {"exported": 9, "skipped": {"no model": 2}}}
        res = mk.promotion_checks(self.records(objects, ids), own, objects, ids, exp)
        self.assertTrue(all(ok for _w, ok in res), res)
        self.assertEqual([w.split(" (")[0] for w, _ok in res][2:],
                         ["1 CONT = 1 distinct containers edids", "1 MISC = 1 distinct items edids",
                          "1 ACTI = 1 distinct activators edids", "1 TERM = 1 distinct terminals edids",
                          "1 TMLM = 1 distinct terminals menu edids", "every promoted REFR names its CONT / MISC / ACTI / TERM"])
        self.assertTrue(res[0][0].endswith("+ 1 containers + 1 items + 2 activators + 2 terminals"), res[0][0])
        for override, why in (({"acti_name": "Gong"}, "ACTI name"), ({"menu": 0x80C}, "does not name its menu"),
                              ({"bodies": []}, "body texts"), ({"bodies": [self.BODY, self.BODY]}, "body texts"),
                              ({"bodies": ["other"]}, "body texts"), ({"isiz": 1}, "no menu item")):
            pp = mk.promoted_record_check(self.records(objects, ids, **override), own, objects, ids)
            self.assertIn(why, pp[0] if pp else "", override)
        menuless = [r for r in self.records(objects, ids) if r["sig"] != "TMLM"]
        res = dict((w.split(" (")[0], ok) for w, ok in mk.promotion_checks(menuless, own, objects, ids, exp))
        self.assertFalse(res["0 TMLM = 1 distinct terminals menu edids"])
        self.assertIn("is not a TMLM", " ".join(mk.promoted_record_check(menuless, own, objects, ids)))
        unnamed = json.loads(json.dumps(objects))
        for e in unnamed["activators"]:
            e["name"] = None                                                 # an unnamed ACTI must have no FULL
        self.assertTrue(mk.promoted_record_check(self.records(objects, ids), own, unnamed, ids))

    def test_nonfinite_values_never_pass_the_record_check(self):
        """Codex's review of #235: abs(NaN - x) > tol is False, so a NaN in the plugin passed the tolerance tests."""
        _cl, objects, ids = self.plan()
        own = 0x01000000
        self.assertEqual(mk.promoted_record_check(self.records(objects, ids), own, objects, ids), [])
        nan = float("nan")
        for channel in range(6):                                            # DATA x, y, z, rx, ry, rz of one REFR
            recs = self.records(objects, ids)
            r = next(r for r in recs if r["fid"] == own | 0x806)
            vals = list(struct.unpack("<6f", r["fields"][1][1]))
            vals[channel] = nan
            r["fields"][1] = (b"DATA", struct.pack("<6f", *vals))
            self.assertTrue(mk.promoted_record_check(recs, own, objects, ids), channel)
        recs = self.records(objects, ids)
        next(r for r in recs if r["fid"] == own | 0x806)["fields"].append((b"XSCL", struct.pack("<f", nan)))
        self.assertTrue(mk.promoted_record_check(recs, own, objects, ids))
        recs = self.records(objects, ids)
        m = next(r for r in recs if r["sig"] == "MISC")
        m["fields"][3] = (b"DATA", struct.pack("<if", 1, nan))
        self.assertIn("MISC DATA", " ".join(mk.promoted_record_check(recs, own, objects, ids)))
        bad = json.loads(json.dumps(objects))
        bad["items"][0]["weight"] = nan                                    # a NaN on the expected side too
        self.assertIn("MISC DATA", " ".join(mk.promoted_record_check(self.records(objects, ids), own, bad, ids)))
        self.assertFalse(mk.close([1.0, 2.0], [1.0], 1))                     # lengths must agree
        self.assertFalse(mk.close(float("inf"), float("inf"), 1))
        self.assertTrue(mk.close([1.0, 2.0], [1.0005, 2.0], 1e-3))

    def test_record_text_reads_utf8_then_cp1252(self):
        self.assertEqual(mk.record_text("Café".encode("utf-8") + b"\0junk"), "Café")
        self.assertEqual(mk.record_text("Café".encode("cp1252") + b"\0"), "Café")
        self.assertIsNone(mk.record_text(None))


def light_base(**kw):
    b = {"editor_id": "defaultLightFire01NSFlicker", "time": -1, "radius": 3.657143, "color": [237, 168, 122], "flags": 1,
         "type": 0, "falloff": 1.0, "fov": 90.0, "near_clip": 0.103106, "flicker": [0.36, 0.8, 0.011], "flicker_effect": 1,
         "lumens": 17655, "bounds": [[-0.1, -0.1, -0.2], [0.1, 0.1, 0.1]], "random_anim_start": False,
         "intensity_scale": 3.96, "dropped": []}
    b.update(kw)
    return b


class LightTests(unittest.TestCase):
    """Exterior lights (docs/terrain/exterior-lights.md): make_cluster.py lights -> objects.json lights for TerrainOverlays."""
    OV = {"cell_min": -32, "cell_max": 31}
    CLUSTER = {"light_bases": {"08ADFA:Fallout4.esm": light_base(), "0517B0:Fallout4.esm": light_base(type=2, flicker_effect=0)},
               "lights": [{"src": "000003:Fallout4.esm", "base": "0517B0:Fallout4.esm", "editor_id": "x",
                           "fo4_pos": [-69139.6, 80740.2, 7825.27], "rot": [0, 0, 1.5], "scale": 1.0, "disabled": False,
                           "radius_delta": -0.5, "lighting": {"fov": -39.2, "fade": 1.6, "near_clip": 0.0},
                           "record_flags": 0x30100},
                          {"src": "000001:Fallout4.esm", "base": "08ADFA:Fallout4.esm", "editor_id": "y",
                           "fo4_pos": [700.0, -1400.0, 70.0], "rot": [0, 0, 0], "scale": 1.0, "disabled": True,
                           "radius_delta": None, "lighting": None, "record_flags": 0},
                          {"src": "000002:Fallout4.esm", "base": "0517B0:Fallout4.esm", "editor_id": "x",
                           "fo4_pos": [9999999.0, 0.0, 0.0], "rot": [0, 0, 0], "scale": 1.0, "disabled": False,
                           "radius_delta": None, "lighting": None, "record_flags": 0x100}]}

    def test_light_edid(self):
        self.assertEqual(mk.light_edid("08ADFA:Fallout4.esm"), "FO4Core_ligh_08adfa_fallout4")
        self.assertNotEqual(mk.light_edid("08ADFA:Fallout4.esm"), mk.light_edid("08ADFA:DLCCoast.esm"))
        with self.assertRaises(ValueError):
            mk.light_edid("Fire")

    def test_lights_in_metres_and_cells_bases_in_first_use_order(self):
        lights, bases, outside = mk.cluster_lights(self.CLUSTER, self.OV, ["000009:Fallout4.esm"])
        self.assertEqual([e["src"] for e in lights], ["000003:Fallout4.esm", "000001:Fallout4.esm"])
        self.assertEqual([b["edid"] for b in bases], ["FO4Core_ligh_0517b0_fallout4", "FO4Core_ligh_08adfa_fallout4"])
        self.assertEqual(bases[0]["fo4_base"], "0517B0:Fallout4.esm")
        self.assertNotIn("dropped", bases[0])                       # report-only keys stay out of objects.json
        e = lights[0]
        self.assertEqual(e["pos"], [round(-69139.6 / 70, 5), round(80740.2 / 70, 5), round(7825.27 / 70, 5)])
        self.assertEqual(e["cell"], list(tg.sf_cell_of(e["pos"][0], e["pos"][1])))
        self.assertEqual((e["radius"], e["lighting"], e["edid"]), (-0.5, {"fov": -39.2, "fade": 1.6, "near_clip": 0.0},
                                                                   "FO4Core_ligh_0517b0_fallout4"))
        self.assertEqual((lights[1]["disabled"], lights[1]["lighting"]), (True, None))
        # the FO4 reference's DoesNotLightWater / NeverFades / DoesNotLightLandscape bits reach objects.json as they are
        self.assertEqual([e["flags"] for e in lights], [0x30100, 0])
        self.assertEqual([s["formkey"] for s in outside], ["000002:Fallout4.esm"])
        self.assertEqual(outside[0]["reason"], "outside_terrain")

    def test_refusals(self):
        c = self.CLUSTER
        cases = [(dict(c), ["000001:fallout4.esm"], "placed reference"),        # a placed (reserved) source, any case
                 ({**c, "lights": c["lights"] + [dict(c["lights"][0])]}, [], "twice"),
                 ({**c, "lights": [dict(c["lights"][0], reference_index=4)]}, [], "reference_index"),
                 ({**c, "lights": [dict(c["lights"][0], base="111111:Fallout4.esm")]}, [], "not in light_bases"),
                 ({**c, "lights": [dict(c["lights"][0], lighting={"fov": 0, "fade": 2.5, "near_clip": 0})]}, [], "vanilla XLIG"),
                 ({**c, "lights": [dict(c["lights"][0], src="")]}, [], "source key"),
                 ({**c, "lights": [dict(c["lights"][0], record_flags=0x800)]}, [], "record_flags"),     # not a carried bit
                 ({**c, "lights": [{k: v for k, v in c["lights"][0].items() if k != "record_flags"}]}, [], "run make_cluster"),
                 ({**c, "light_bases": {"0517B0:Fallout4.esm": light_base(lumens=0)}}, [], "out of range"),
                 ({**c, "light_bases": {"0517B0:Fallout4.esm": {k: v for k, v in light_base().items() if k != "fov"}}}, [], "missing")]
        for cluster, placed, why in cases:
            with self.assertRaisesRegex(ValueError, why):
                mk.cluster_lights(cluster, self.OV, placed)
        self.assertEqual(mk.cluster_lights({}, self.OV, []), ([], [], []))

    def test_stage_lights_keeps_the_export_accounting(self):
        skipped = [{"formkey": s, "reason": "type_not_translated"} for s in ("000001:Fallout4.esm", "000002:Fallout4.esm",
                                                                             "000003:Fallout4.esm", "00000A:Fallout4.esm")]
        placed = [{"src": "000009:Fallout4.esm"}]
        lights, bases, left, n_out = mk.stage_lights(self.CLUSTER, self.OV, placed, [], skipped)
        self.assertEqual(n_out, 1)
        self.assertEqual(len(placed) + len(lights) + len(left), 1 + len(skipped))
        self.assertEqual(sorted((s["formkey"], s["reason"]) for s in left),
                         [("000002:Fallout4.esm", "outside_terrain"), ("00000A:Fallout4.esm", "type_not_translated")])
        with self.assertRaisesRegex(ValueError, "did not skip"):
            mk.stage_lights(self.CLUSTER, self.OV, placed, [], skipped[1:])  # a light that is not in this export
        self.assertEqual(mk.stage_lights({}, self.OV, placed, [], skipped)[2], skipped)

    def ids(self):
        objects = {"refs": [{"src": "R1"}], "containers": [{"src": "C1", "reference_index": 0}],
                   "lights": [{"src": "L1", "edid": "B"}, {"src": "L2", "edid": "A"}, {"src": "L3", "edid": "B"}],
                   "light_bases": [{"edid": "B"}, {"edid": "A"}]}
        ids = {"bases": {"S": "000900"}, "refs": {"R1": "000902"}, "containers": {"C1": {"base": "000903", "ref": "000901"}},
               "navmeshes": ["000904", "000905"],
               "lights": {"L1": {"base": "000909", "ref": "000906"}, "L2": {"base": "00090A", "ref": "000907"},
                          "L3": {"base": "000909", "ref": "000908"}}}
        return objects, ids

    def test_light_ids_follow_every_other_record(self):
        objects, ids = self.ids()
        mk.check_light_identities(objects, ids)
        mk.check_light_identities({"refs": []}, {})                 # no lights: nothing to check
        bad = copy.deepcopy(ids)
        bad["lights"]["L1"]["ref"] = "000904"                       # inside the NAVM range
        bad["lights"]["L2"]["ref"], bad["lights"]["L3"]["ref"] = "000905", "000906"
        with self.assertRaisesRegex(ValueError, "not new id"):
            mk.check_light_identities(objects, bad)
        bad = copy.deepcopy(ids)
        bad["lights"]["L3"]["base"] = "00090A"                      # one edid, two LIGH
        with self.assertRaisesRegex(ValueError, "LIGH"):
            mk.check_light_identities(objects, bad)
        bad = copy.deepcopy(ids)
        bad["items"] = {"I1": {"base": "000910", "ref": "000911"}}  # a later promoted class (#235) counts as "other"
        with self.assertRaisesRegex(ValueError, "not new id"):
            mk.check_light_identities(objects, bad)
        bad = copy.deepcopy(ids)
        del bad["lights"]["L2"]
        with self.assertRaisesRegex(ValueError, "differs"):
            mk.check_light_identities(objects, bad)
        swapped = copy.deepcopy(objects)
        swapped["light_bases"].reverse()
        with self.assertRaisesRegex(ValueError, "first-use"):
            mk.check_light_identities(swapped, ids)

    def test_light_ids_follow_terminal_menus(self):
        # merged with #241: a promoted terminal's TMLM menu is one of the other records, so the lights come after it
        objects, ids = self.ids()
        with_menu = copy.deepcopy(ids)
        with_menu["terminals"] = {"T1": {"base": "000903", "ref": "000901", "menu": "000906"}}
        with self.assertRaisesRegex(ValueError, "not new id"):
            mk.check_light_identities(objects, with_menu)
        for src, v in with_menu["lights"].items():
            with_menu["lights"][src] = {k: f"{int(x, 16) + 1:06X}" for k, x in v.items()}
        mk.check_light_identities(objects, with_menu)

    def test_lights_after_and_raw_record_check(self):
        objects, ids = self.ids()
        own = 1 << 24
        recs = [{"sig": "STAT", "fid": own | 0x900, "flags": 0, "fields": []},
                {"sig": "NAVM", "fid": own | 0x905, "flags": 0, "fields": []},
                {"sig": "NAVI", "fid": 0x000FF1, "flags": 0, "fields": []},       # an override of a master's record
                {"sig": "LIGH", "fid": own | 0x909, "flags": 0, "fields": []},
                {"sig": "REFR", "fid": own | 0x906, "flags": 0x100, "fields": []}]
        self.assertEqual(mk.lights_after(recs, 1, ids), (0x906, 0x905))
        recs.append({"sig": "REFR", "fid": own | 0x90B, "flags": 0, "fields": []})  # a non-light record after the lights
        first, last = mk.lights_after(recs, 1, ids)
        self.assertLess(first, last)
        # light_record_problems on hand-made raw records: a LIGH with a wrong lumens value, a REFR without the 0x100 flag
        dat2 = bytearray(76)
        struct.pack_into("<ifBBBBI", dat2, 0, -1, 3.657143, 237, 168, 122, 0, 1)
        struct.pack_into("<I", dat2, 52, 17000)
        dat2[56], dat2[57] = 0, 1
        edid = "FO4Core_ligh_08adfa_fallout4"
        lobj = {"lights": [{"src": "L1", "edid": edid, "pos": [1, 2, 3], "rot": [0, 0, 0], "scale": 1.0,
                            "disabled": False, "radius": None, "lighting": None, "flags": 0x100}],
                "light_bases": [dict(light_base(), edid=edid)]}
        lids = {"lights": {"L1": {"base": "000909", "ref": "000906"}}}
        raw = [{"sig": "LIGH", "fid": own | 0x909, "flags": 0, "fields": [(b"EDID", edid.encode() + b"\0"), (b"DAT2", bytes(dat2))]},
               {"sig": "REFR", "fid": own | 0x906, "flags": 0, "fields": [(b"NAME", struct.pack("<I", own | 0x909)),
                                                                          (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0))]}]
        problems = mk.light_record_problems(raw, own, lobj, lids)
        self.assertEqual(len(problems), 2)
        self.assertIn("lumens 17000", problems[0])
        self.assertIn("flags", problems[1])
        struct.pack_into("<I", dat2, 52, 17655)
        raw[0]["fields"][1] = (b"DAT2", bytes(dat2))
        raw[1]["flags"] = 0x100
        self.assertEqual(mk.light_record_problems(raw, own, lobj, lids), [])
        # the REFR carries the FO4 reference's own light bits (the review of #246), not a forced 0x100
        lobj["lights"][0]["flags"] = 0x30100                       # DoesNotLightWater | NeverFades | DoesNotLightLandscape
        self.assertTrue(any("flags" in p for p in mk.light_record_problems(raw, own, lobj, lids)))
        raw[1]["flags"] = 0x30100
        self.assertEqual(mk.light_record_problems(raw, own, lobj, lids), [])
        lobj["lights"][0]["flags"] = 0                             # a FO4 light that lights water
        raw[1]["flags"] = 0x100
        self.assertTrue(any("flags" in p for p in mk.light_record_problems(raw, own, lobj, lids)))
        raw[1]["flags"] = 0
        self.assertEqual(mk.light_record_problems(raw, own, lobj, lids), [])

    def test_raw_record_check_reports_undeclared_lights_instead_of_raising(self):
        # the review of #246 (P3-2): a formids.json without "lights" (an older or failed build) or a light base no
        # light uses is a listed problem, so check reports its failed checks instead of stopping with a KeyError
        edid = "FO4Core_ligh_08adfa_fallout4"
        lobj = {"lights": [{"src": "L1", "edid": edid, "pos": [1, 2, 3], "rot": [0, 0, 0], "scale": 1.0,
                            "disabled": False, "radius": None, "lighting": None, "flags": 0x100}],
                "light_bases": [dict(light_base(), edid=edid), dict(light_base(), edid="FO4Core_ligh_unused")]}
        problems = mk.light_record_problems([], 1 << 24, lobj, {"bases": {}})
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(all("declared" in p for p in problems))

    def test_promotion_checks_count_the_lights(self):
        # merged with #235: the REFR total and the export accounting include the lights, which left the skipped list
        own = 1 << 24
        objects = {"refs": [{"src": "R1"}], "lights": [{"src": "L1"}, {"src": "L2"}]}
        recs = [{"sig": "REFR", "fid": own | 0x800 + k, "flags": 0, "fields": []} for k in range(5)]   # + COC, anchor
        exp = {"objects": {"exported": 5, "skipped": {"no model": 2}}}
        res = mk.promotion_checks(recs, own, objects, {}, exp)
        self.assertEqual([ok for _w, ok in res], [True, True], res)
        self.assertIn("+ 2 lights", res[0][0])
        res = mk.promotion_checks(recs[:-1], own, objects, {}, exp)
        self.assertFalse(res[0][1])                                # one light REFR short
