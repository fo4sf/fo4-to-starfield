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

    def test_a_model_placed_as_a_teleporting_door_is_converted_as_a_load_door(self):
        door = {"formkey": "000009:Fallout4.esm", "type": "Door", "model": "SetDressing\\Elevator\\Lift01.nif",
                "teleport_destination": {"door": "00000A:Fallout4.esm"}}
        plain = dict(door, formkey="00000B:Fallout4.esm", teleport_destination=None)
        self.assertTrue(mk.slim(door)["teleports"])
        self.assertNotIn("teleports", mk.slim(plain))
        for refs in ([plain, door], [door, plain]):
            self.assertEqual(mk.convert_list([mk.slim(r) for r in refs])[0]["teleport_destination"], True)
        self.assertNotIn("teleport_destination", mk.convert_list([mk.slim(plain)])[0])

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
        dry._texture_set("set_ts", "a_d.dds", "a_n.dds", "", two_sided=True)
        self.assertEqual(dry.outputs["set1"], [("color", "BC1", 1024, 512), ("normal", "BC5", 512, 512),
                                               ("rough", "BC4", 256, 256), ("opacity", "BC4", 1024, 512)])
        self.assertEqual(dry.outputs["set2"][2], ("rough", "BC4", 128, 128))      # no spec: a quarter of the normal
        self.assertNotIn("opacity", [k for k, *_ in dry.outputs["set_ts"]])       # two_sided alone is not a cutout
        with self.assertRaises(FileNotFoundError):
            dry._texture_set("set3", "missing_d.dds", "a_n.dds", "")

        class Src:
            def __init__(self):
                self.textures = [Arc()]

            def material(self, path):
                head = bytearray(b"BGSM" + struct.pack("<II4f", 2, 3, 0.0, 0.0, 1.0, 1.0) + b"\x00" * 35)
                head[48] = 1
                def s(t):
                    b = t.encode() + b"\0"
                    return struct.pack("<I", len(b)) + b
                return bytes(head) + s("a_d.dds") + s("a_n.dds") + s("") + s("") + s("") + s("") + b"\x00" * 40

        dry2 = mk.DryConverter(Src())
        got = dry2.conv.material("materials/car00.bgsm")
        self.assertIsNotNone(got)
        self.assertEqual(dry2.conv.stats["materials_fallback"], 0)
        self.assertNotIn("opacity", [k for k, *_ in dry2.outputs["car00"]])


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
    def test_plugin_punctuation_and_extension_do_not_merge_source_bases(self):
        plugins = ("SomeDLC.esm", "Some-DLC.esm", "Some_DLC.esm", "Some.DLC.esm", "SomeDLC.esp", "SomeDLC.esl")
        keys = [mk.container_edid(f"04B6E9:{plugin}", "000001:Fallout4.esm") for plugin in plugins]
        self.assertEqual(len(set(keys)), len(plugins))
        for plugin, key in zip(plugins, keys):
            self.assertEqual(mk.container_edid(f"04b6e9:{plugin.upper()}", "000002:Fallout4.esm"), key)

    def test_existing_simple_master_and_r05_names_stay_stable(self):
        for plugin, suffix in (("Fallout4.esm", "fallout4"), ("DLCCoast.esm", "dlccoast"), ("DLCNukaWorld.esm", "dlcnukaworld")):
            self.assertEqual(mk.container_edid(f"04B6E9:{plugin}", "x"), f"FO4Core_cont_04b6e9_{suffix}")
        self.assertEqual(mk.container_edid(None, "19EE52:Fallout4.esm"), "FO4Core_cont_19ee52")

    def test_unshared_reference_keys_keep_the_source_plugin(self):
        refs = ("19EE52:Fallout4.esm", "19EE52:SomeDLC.esm", "19EE52:SomeDLC.esp")
        self.assertEqual(len({mk.container_edid(None, src) for src in refs}), len(refs))
        self.assertEqual(mk.container_edid(None, refs[-1]), mk.container_edid(None, refs[-1].upper()))

    def test_unicode_expansion_cannot_alias_another_plugin_name(self):
        self.assertNotEqual(mk.container_edid("04B6E9:Ma\u00dfe.esm", "x"), mk.container_edid("04B6E9:Masse.esm", "x"))
        self.assertNotEqual(mk.container_edid(None, "19EE52:Ma\u00dfe.esm"), mk.container_edid(None, "19EE52:Masse.esm"))

    def test_key_collision_is_refused_even_when_metadata_matches(self):
        from unittest.mock import patch
        bases = [{"model": "synthetic.nif"}]
        placed = [{"src": f"{i:06X}:Fallout4.esm", "base": 0, "cell": [0, 0], "pos": [0, 0, 0],
                   "rot": [0, 0, 0], "scale": 1.0} for i in (1, 2)]
        cluster = {"containers": [{"src": p["src"], "base": base, "name": "Box",
                                   "items": [{"form": "Starfield.esm:00000F", "count": 1}]}
                                  for p, base in zip(placed, ("04B6E9:SomeDLC.esm", "04B6E9:Other.esm"))]}
        with patch.object(mk, "container_edid", return_value="ForcedCollision"):
            with self.assertRaisesRegex(ValueError, "distinct source identities"):
                mk.cluster_containers(bases, placed, cluster)

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
        marked = dict(ids, map_marker_refs={"W": {"RedRocket": "00080C", "Concord": "00080D"}})
        res = mk.promotion_checks(recs + [{"sig": "REFR", "fid": own | 0x80C + k, "flags": 0, "fields": []}
                                          for k in range(2)], own, objects, marked, exp)
        self.assertTrue(res[0][1] and "2 map markers" in res[0][0], res[0])            # the map markers counted
        self.assertFalse(mk.promotion_checks(recs, own, objects, marked, exp)[0][1])

    def test_params_view_leaves_out_map_markers(self):
        core = {"plugin": "P.esm", "overlays": [{"world": "W", "spawn": [1, 2, 3]}]}
        staged = {"plugin": "P.esm", "objects": "objects.json",
                  "overlays": [{"world": "W", "spawn": [1, 2, 3], "map_markers": [{"tag": "RedRocket"}]}]}
        self.assertEqual(mk.core_params_view(staged), core)
        self.assertNotEqual(mk.core_params_view(dict(staged, overlays=[{"world": "X", "map_markers": []}])), core)


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
                         {"containers": [6], "items": [0], "activators": [1, 3], "terminals": [4, 5], "workshops": [], "flora": [], "doors": [], "benches": []})
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
        from unittest.mock import patch
        # Full plugin identities are distinct, while an actual forced collision still refuses.
        cl = {"activators": [self.acti(1, base="0BB1E1:A-B.esm"), self.acti(3, base="0BB1E1:AB.esp")]}
        entries = mk.cluster_promote(self.BASES, self.placed(), cl)[1]["activators"]
        self.assertEqual(len({e["edid"] for e in entries}), 2)
        self.assertEqual([e["reference_index"] for e in entries], [1, 3])
        with patch.object(mk, "promoted_edid", return_value="ForcedCollision"):
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


class FloraPromotionTests(unittest.TestCase):
    """Harvestable plants (docs/terrain/flora.md): --cluster "flora" become native FLOR with PFIG the ingredient."""
    BASES = [{"edid": "FO4Core_melon", "model": "fo4core\\setdressing\\flora\\florawildmelonvine01.nif"},
             {"edid": "FO4Core_tato", "model": "fo4core\\setdressing\\flora\\floratatoplant01.nif"}]
    ING = "00260DF2:Starfield.esm"

    @staticmethod
    def placed(n=5, disabled=()):
        return [{"src": f"{i + 1:06X}:Fallout4.esm", "base": 0 if i < 3 else 1, "cell": [0, i],
                 "pos": [1.0 + i, 2.0, 3.0], "rot": [0, 0, 0.5], "scale": 1.0, "disabled": i in disabled}
                for i in range(n)]

    @classmethod
    def plant(cls, i, **kw):
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "name": "Melon Vine", "base": "01C25E:Fallout4.esm",
             "editor_id": "FloraWildMelonVine01", "ingredient": cls.ING}
        e.update(kw)
        return e

    def test_flora_of_one_base_share_the_flor_and_carry_the_ingredient(self):
        cl = {"flora": [self.plant(1), self.plant(0), self.plant(3, base="01C25F:Fallout4.esm", name="Tato")]}
        keep, out = mk.cluster_flora(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], ["000003:Fallout4.esm", "000005:Fallout4.esm"])
        self.assertEqual([e["edid"] for e in out],
                         ["FO4Core_flor_01c25e_fallout4", "FO4Core_flor_01c25e_fallout4", "FO4Core_flor_01c25f_fallout4"])
        self.assertEqual([e["reference_index"] for e in out], [0, 1, 3])
        self.assertEqual([e["ingredient"] for e in out], [self.ING, self.ING, self.ING])
        e = out[0]
        self.assertEqual((e["model"], e["name"], e["cell"], e["pos"]),
                         (self.BASES[0]["model"], "Melon Vine", [0, 0], [1.0, 2.0, 3.0]))
        self.assertEqual(mk.flora_edid(None, "01C25E:Fallout4.esm"), "FO4Core_flor_01c25e")
        self.assertEqual(mk.cluster_flora(self.BASES, self.placed(), {}), (self.placed(), []))
        no_ing = self.plant(0)
        del no_ing["ingredient"]
        self.assertEqual(mk.cluster_flora(self.BASES, self.placed(), {"flora": [no_ing]})[1][0]["ingredient"], self.ING)
        import make_cluster as mc
        self.assertEqual(mk.FLORA_INGREDIENT, mc.FLORA_INGREDIENT)

    def test_bad_flora_entries_are_refused(self):
        P = self.placed()
        cases = (
            {"flora": [self.plant(0), self.plant(1, name="Gourd")]},
            {"flora": [self.plant(0), self.plant(3)]},
            {"flora": [self.plant(0, name="")]},
            {"flora": [self.plant(0, name="a\nb")]},
            {"flora": [self.plant(0, name=None)]},
            {"flora": [self.plant(0), self.plant(0)]},
            {"flora": [self.plant(0, src="ABCDEF:Fallout4.esm")]},
            {"flora": [self.plant(0, ingredient="not-a-form")]},
            {"flora": [self.plant(0, ingredient="00260DF2:Fallout4.esm")]},
        )
        for cl in cases:
            with self.assertRaises(ValueError, msg=cl):
                mk.cluster_flora(self.BASES, P, cl)
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_flora(self.BASES, self.placed(disabled=(0,)), {"flora": [self.plant(0)]})

    def test_flora_joins_the_one_slot_plan(self):
        cl = {"flora": [self.plant(2)], "activators": [{"src": "000001:Fallout4.esm", "name": "Bell",
                                                        "base": "0BB1E1:Fallout4.esm"}]}
        keep, promoted = mk.cluster_promote(self.BASES, self.placed(), cl)
        self.assertEqual({k: [e["reference_index"] for e in v] for k, v in promoted.items() if v},
                         {"flora": [2], "activators": [0]})
        cl["activators"].append({"src": "000003:Fallout4.esm", "name": "Bell", "base": "0BB1E1:Fallout4.esm"})
        with self.assertRaisesRegex(ValueError, "listed as both an activator and a flora"):
            mk.cluster_promote(self.BASES, self.placed(), cl)

    def test_flora_record_check_wants_organic_keyword_and_pfig(self):
        keep, out = mk.cluster_flora(self.BASES, self.placed(), {"flora": [self.plant(0)]})
        objects = {"refs": keep, "flora": out}
        ids = {"bases": {"a": "000800"}, "refs": {p["src"]: f"{0x802 + i:06X}" for i, p in enumerate(keep)},
               "flora": {out[0]["src"]: {"base": "000810", "ref": "000801"}}}
        own = 0x01000000

        def z(text):
            return text.encode("utf-8") + b"\0"

        recs = [{"sig": "REFR", "fid": own | 0x801, "flags": 0,
                 "fields": [(b"NAME", struct.pack("<I", own | 0x810)),
                            (b"DATA", struct.pack("<6f", *out[0]["pos"], *out[0]["rot"]))]},
                {"sig": "FLOR", "fid": own | 0x810, "flags": 0, "fields": [
                    (b"EDID", z(out[0]["edid"])), (b"FULL", z(out[0]["name"])), (b"MODL", z(out[0]["model"])),
                    (b"KSIZ", struct.pack("<I", 1)), (b"KWDA", struct.pack("<I", 0x00222E03)),
                    (b"PFIG", struct.pack("<I", 0x00260DF2))]}]
        recs += [{"sig": "REFR", "fid": own | int(v, 16), "flags": 0, "fields": []} for v in ids["refs"].values()]
        recs += [{"sig": "REFR", "fid": own | 0x820, "flags": 0, "fields": []},
                 {"sig": "REFR", "fid": own | 0x821, "flags": 0, "fields": []}]
        self.assertEqual(mk.promoted_record_check(recs, own, objects, ids), [])
        recs_no_pfig = [dict(r) for r in recs]
        recs_no_pfig[1] = dict(recs[1], fields=[f for f in recs[1]["fields"] if f[0] != b"PFIG"])
        self.assertTrue(any("PFIG" in p for p in mk.promoted_record_check(recs_no_pfig, own, objects, ids)))
        recs_no_kw = [dict(r) for r in recs]
        recs_no_kw[1] = dict(recs[1], fields=[f for f in recs[1]["fields"] if f[0] not in (b"KWDA", b"KSIZ")])
        self.assertTrue(any("FloraTypeOrganic" in p for p in mk.promoted_record_check(recs_no_kw, own, objects, ids)))


def light_base(**kw):
    b = {"editor_id": "defaultLightFire01NSFlicker", "time": -1, "radius": 3.657143, "color": [237, 168, 122], "flags": 1,
         "type": 0, "falloff": 1.0, "fov": 90.0, "near_clip": 0.103106, "flicker": [0.36, 0.8, 0.011], "flicker_effect": 1,
         "lumens": 17655, "bounds": [[-0.1, -0.1, -0.2], [0.1, 0.1, 0.1]], "random_anim_start": False,
         "intensity_scale": 3.96, "dropped": []}
    b.update(kw)
    return b


class GarageButtonTests(unittest.TestCase):
    """Playtest row 21: the two Commonwealth RedRGarageDoor / RedR_ButtonBox pairs (docs/terrain/garage-button.md)."""

    def test_pairs_only_when_both_activators_are_promoted(self):
        shop = [{"src": "00056331:Fallout4.esm"}, {"src": "00056BBA:Fallout4.esm"}]
        self.assertEqual(mk.cluster_garage_buttons(shop), [
            {"door": "00056331:Fallout4.esm", "button": "00056BBA:Fallout4.esm"}])
        self.assertEqual(mk.cluster_garage_buttons(shop + [{"src": "000866C7:Fallout4.esm"},
                                                           {"src": "000866C0:Fallout4.esm"}]), [
            {"door": "00056331:Fallout4.esm", "button": "00056BBA:Fallout4.esm"},
            {"door": "000866C7:Fallout4.esm", "button": "000866C0:Fallout4.esm"}])
        self.assertEqual(mk.cluster_garage_buttons([{"src": "00056BBA:Fallout4.esm"}]), [])
        short = [{"src": "056331:Fallout4.esm"}, {"src": "056BBA:Fallout4.esm"}]
        self.assertEqual(mk.cluster_garage_buttons(short), [
            {"door": "056331:Fallout4.esm", "button": "056BBA:Fallout4.esm"}])

    def test_pairs_keep_plugin_identity(self):
        foreign = [{"src": "00056331:Other.esm"}, {"src": "00056BBA:Other.esm"}]
        self.assertEqual(mk.cluster_garage_buttons(foreign), [])
        mixed = [{"src": "00056331:Fallout4.esm"}, {"src": "00056BBA:Other.esm"}]
        self.assertEqual(mk.cluster_garage_buttons(mixed), [])
        shadow = [{"src": "00056331:Fallout4.esm"}, {"src": "00056BBA:Fallout4.esm"},
                  {"src": "00056331:Other.esm"}]
        self.assertEqual(mk.cluster_garage_buttons(shadow), [
            {"door": "00056331:Fallout4.esm", "button": "00056BBA:Fallout4.esm"}])
        with self.assertRaisesRegex(ValueError, "same FO4 source"):
            mk.cluster_garage_buttons([{"src": "00056331:Fallout4.esm"}, {"src": "056331:Fallout4.esm"}])

    def test_vmad_linked_ref_keyword_matches_xlkr(self):
        door = 0x01000DB0
        vmad = mk.garage_button_vmad()
        xlkr = mk.garage_button_xlkr(door)
        props = mk.vmad_patch.decode(vmad)["scripts"][0]["properties"]
        self.assertEqual(props[0]["name"], mk.GARAGE_SCRIPT_PROPERTY)
        self.assertEqual(props[0]["value"]["form"], mk.GARAGE_LINK_KEYWORD)
        self.assertEqual(struct.unpack("<II", xlkr), (mk.GARAGE_LINK_KEYWORD, door))
        path = os.path.join(root, "dotnet", "TerrainOverlays", "Program.cs")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("LinkedRefKeyword", src)
        self.assertIn("0x5D5E7", src)
        self.assertIn("DefaultActivateLinkedRefOnActivate", src)


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


class StationPromotionTests(unittest.TestCase):
    """Stations (docs/terrain/stations.md): --cluster "workshops" become native ACTI build stations (one per FO4 base,
    WorkshopKeyword + outpost categories, PRPS build radius) and "benches" keep their slot on the vanilla Starfield
    bench of their kind, both in the one slot plan with the other classes."""
    BASES = [{"edid": "FO4Core_workbenchgarage01", "model": "fo4core\\setdressing\\garage\\workbenchgarage01.nif"},
             {"edid": "FO4Core_workbenchweaponsa", "model": "fo4core\\furniture\\workstations\\workbenchweaponsa.nif"},
             {"edid": "FO4Core_workstationarmorb01", "model": "fo4core\\furniture\\workstations\\workstationarmorb01.nif"}]

    @staticmethod
    def placed(n=8, disabled=()):
        base = {4: 1, 5: 2, 6: 1}
        return [{"src": f"{i + 1:06X}:Fallout4.esm", "base": base.get(i, 0), "cell": [0, i], "pos": [1.0 + i, 2.0, 3.0],
                 "rot": [0, 0, 0.5], "scale": 1.0, "disabled": i in disabled} for i in range(n)]

    @staticmethod
    def wk(i, **kw):
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "name": "Workshop", "radius": 250.0, "base": "0C1AEB:Fallout4.esm",
             "editor_id": "WorkshopWorkbench"}
        e.update(kw)
        return e

    @staticmethod
    def bench(i, kind="weapon", **kw):
        van = mk.BENCH_VANILLA.get(kind, ("2B6A63:Starfield.esm", 2))
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "kind": kind, "vanilla": van[0], "base": "17B3A4:Fallout4.esm",
             "editor_id": "workbenchWeaponsA", "wbdt": van[1]}
        e.update(kw)
        return e

    def test_constants_match_make_cluster(self):
        import make_cluster as mc
        self.assertEqual((mk.WORKSHOP_NAME, mk.WORKSHOP_RADIUS_M, mk.WORKSHOP_KEYWORD), (mc.WORKSHOP_NAME, mc.WORKSHOP_RADIUS_M, mc.WORKSHOP_KEYWORD))
        self.assertEqual({k: v[0] for k, v in mk.BENCH_VANILLA.items()}, {k: v["vanilla"] for k, v in mc.BENCH_KINDS.items()})
        self.assertEqual({k: v[1] for k, v in mk.BENCH_VANILLA.items()}, {k: v["wbdt"] for k, v in mc.BENCH_KINDS.items()})
        self.assertEqual((mk.WORKSHOP_TEMPLATE, mk.WORKSHOP_RADIUS_AV), (0x024DC7, 0x063FC5))
        self.assertEqual(mk.PROMOTED[-3:], (("workshops", "ACTI"), ("flora", "FLOR"), ("doors", "ACTI")))  # doors last (appended)
        self.assertEqual(mk.FLORA_INGREDIENT, mc.FLORA_INGREDIENT)
        self.assertEqual(mk.VANILLA_PROMOTED, (("benches", "FURN"),))
        self.assertEqual(mk.APPENDED, ("doors",))
        self.assertEqual(mk.master_fid("2B6A63:Starfield.esm"), 0x002B6A63)
        self.assertEqual(mk.master_fid("000800:Other.esm", ("Starfield.esm", "other.ESM")), 0x01000800)
        with self.assertRaisesRegex(ValueError, "not a master"):
            mk.master_fid("2B6A63:Fallout4.esm")

    def test_workshops_of_one_base_share_the_acti_and_carry_name_and_radius(self):
        cl = {"workshops": [self.wk(1), self.wk(3), self.wk(2, base="246F86:Fallout4.esm")]}
        keep, out = mk.cluster_workshops(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], [f"{i:06X}:Fallout4.esm" for i in (1, 5, 6, 7, 8)])
        self.assertEqual([e["edid"] for e in out], ["FO4Core_wkshp_0c1aeb_fallout4", "FO4Core_wkshp_246f86_fallout4",
                                                    "FO4Core_wkshp_0c1aeb_fallout4"])
        self.assertEqual([(e["reference_index"], e["name"], e["radius"], e["model"]) for e in out],
                         [(1, "Workshop", 250.0, self.BASES[0]["model"]), (2, "Workshop", 250.0, self.BASES[0]["model"]),
                          (3, "Workshop", 250.0, self.BASES[0]["model"])])
        self.assertEqual((out[0]["cell"], out[0]["pos"], out[0]["rot"], out[0]["scale"]), ([0, 1], [2.0, 2.0, 3.0], [0, 0, 0.5], 1.0))
        bare = {"src": "000002:Fallout4.esm", "base": "0C1AEB:Fallout4.esm"}                   # defaults: name and radius
        self.assertEqual([(e["name"], e["radius"]) for e in mk.cluster_workshops(self.BASES, self.placed(), {"workshops": [bare]})[1]],
                         [("Workshop", 250.0)])
        self.assertEqual(mk.workshop_edid(None, "054BAE:Fallout4.esm"), "FO4Core_wkshp_054bae")

    def test_benches_bind_to_the_vanilla_bench_of_their_kind(self):
        cl = {"benches": [self.bench(4), self.bench(5, "armor", base="12EA9B:Fallout4.esm", editor_id="WorkbenchArmorA"),
                          self.bench(6, "chem"), self.bench(0, "cooking")]}
        keep, out = mk.cluster_benches(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], [f"{i:06X}:Fallout4.esm" for i in (2, 3, 4, 8)])
        self.assertEqual([(e["reference_index"], e["kind"], e["vanilla"], e["fo4_model"]) for e in out],
                         [(0, "cooking", "2B6A65:Starfield.esm", self.BASES[0]["model"]),
                          (4, "weapon", "2B6A63:Starfield.esm", self.BASES[1]["model"]),
                          (5, "armor", "2B6A62:Starfield.esm", self.BASES[2]["model"]),
                          (6, "chem", "2B6A61:Starfield.esm", self.BASES[1]["model"])])
        self.assertNotIn("edid", out[0])                                   # no record of our own
        no_vanilla = self.bench(4)
        del no_vanilla["vanilla"]
        self.assertEqual(mk.cluster_benches(self.BASES, self.placed(), {"benches": [no_vanilla]})[1][0]["vanilla"], "2B6A63:Starfield.esm")
        self.assertEqual(mk.cluster_benches(self.BASES, self.placed(), {"benches": [self.bench(4, vanilla="2b6a63:starfield.ESM")]})[1][0]["vanilla"],
                         "2B6A63:Starfield.esm")

    def test_bad_entries_are_refused(self):
        P = self.placed()
        cases = (
            (mk.cluster_workshops, {"workshops": [self.wk(1), self.wk(3, radius=60.0)]}, "different name / model / radius"),
            (mk.cluster_workshops, {"workshops": [self.wk(1), self.wk(3, name="Settlement")]}, "different name / model / radius"),
            (mk.cluster_workshops, {"workshops": [self.wk(1), self.wk(4)]}, "different name / model / radius"),   # another model
            (mk.cluster_workshops, {"workshops": [self.wk(1, name="a\nb")]}, "not one non-empty line"),
            (mk.cluster_workshops, {"workshops": [self.wk(1, name="")]}, "not one non-empty line"),
            (mk.cluster_workshops, {"workshops": [self.wk(1, radius=0)]}, "float32 number > 0"),
            (mk.cluster_workshops, {"workshops": [self.wk(1, radius=-5.0)]}, "float32 number > 0"),
            (mk.cluster_workshops, {"workshops": [self.wk(1, radius=float("nan"))]}, "float32 number > 0"),
            (mk.cluster_workshops, {"workshops": [self.wk(1, radius="250")]}, "float32 number > 0"),
            (mk.cluster_workshops, {"workshops": [self.wk(1), self.wk(1)]}, "twice"),
            (mk.cluster_workshops, {"workshops": [self.wk(1, src="ABCDEF:Fallout4.esm")]}, "not placed"),
            (mk.cluster_benches, {"benches": [self.bench(4, kind="power")]}, "not one of weapon, armor, chem, cooking"),
            (mk.cluster_benches, {"benches": [self.bench(4, kind=None)]}, "not one of"),
            (mk.cluster_benches, {"benches": [self.bench(4, vanilla="2B6A62:Starfield.esm")]}, "not the weapon bench"),
            (mk.cluster_benches, {"benches": [self.bench(4, vanilla="2B6A63:Fallout4.esm")]}, "not the weapon bench"),
            (mk.cluster_benches, {"benches": [self.bench(4), self.bench(4)]}, "twice"),
        )
        for fn, cl, why in cases:
            with self.assertRaisesRegex(ValueError, why, msg=cl):
                fn(self.BASES, P, cl)
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_benches(self.BASES, self.placed(disabled=(4,)), {"benches": [self.bench(4)]})
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_workshops(self.BASES, self.placed(disabled=(1,)), {"workshops": [self.wk(1)]})

    def plan(self):
        """Every class at once (a container, an item, an activator, a terminal, two workshops of one base, two benches)
        and the identities the writer declares: bases 800..802, slots 803..80A, then CONT, MISC, ACTI, TERM, TMLM,
        the workshops' ACTI; the benches declare the vanilla bench."""
        kit = {"src": "000008:Fallout4.esm", "name": "Kit", "items": [{"form": "Starfield.esm:00000F", "count": 25}], "base": "04B6E9:Fallout4.esm"}
        can = {"src": "000001:Fallout4.esm", "name": "Can", "value": 1, "weight": 0.1, "base": "059B02:Fallout4.esm"}
        bell = {"src": "000004:Fallout4.esm", "name": "Bell", "base": "0BB1E1:Fallout4.esm"}
        term = {"src": "000007:Fallout4.esm", "name": "Terminal", "base": "0E1E33:Fallout4.esm"}
        cl = {"containers": [kit], "items": [can], "activators": [bell], "terminals": [term],
              "workshops": [self.wk(1), self.wk(2)], "benches": [self.bench(4), self.bench(5, "armor")]}
        keep, promoted = mk.cluster_promote(self.BASES, self.placed(), cl)
        self.assertEqual([p["src"] for p in keep], [])
        self.assertEqual({k: [e["reference_index"] for e in v] for k, v in promoted.items()},
                         {"containers": [7], "items": [0], "activators": [3], "terminals": [6], "workshops": [1, 2], "flora": [], "doors": [], "benches": [4, 5]})
        objects = dict({"refs": keep}, **promoted)
        ids = {"bases": {"a": "000800", "b": "000801", "c": "000802"}, "refs": {},
               "containers": {"000008:Fallout4.esm": {"base": "00080B", "ref": "00080A"}},
               "items": {"000001:Fallout4.esm": {"base": "00080C", "ref": "000803"}},
               "activators": {"000004:Fallout4.esm": {"base": "00080D", "ref": "000806"}},
               "terminals": {"000007:Fallout4.esm": {"base": "00080E", "ref": "000809", "menu": "00080F"}},
               "workshops": {"000002:Fallout4.esm": {"base": "000810", "ref": "000804"},
                             "000003:Fallout4.esm": {"base": "000810", "ref": "000805"}},
               "benches": {"000005:Fallout4.esm": {"base": "2B6A63:Starfield.esm", "ref": "000807", "kind": "weapon"},
                           "000006:Fallout4.esm": {"base": "2B6A62:Starfield.esm", "ref": "000808", "kind": "armor"}}}
        mk.check_reference_slots(objects, ids)
        return cl, objects, ids

    def test_every_class_shares_one_slot_plan(self):
        cl, _objects, _ids = self.plan()
        for k, other in (("workshops", "containers"), ("benches", "activators"), ("containers", "workshops"), ("items", "benches")):
            two = json.loads(json.dumps(cl))
            e = dict(two[k][0])
            if other == "benches":
                e.update(kind="weapon")
            if other == "containers":
                e.update(items=[{"form": "Starfield.esm:00000F", "count": 1}], name="X")
            two[other].append(e)
            with self.assertRaisesRegex(ValueError, "listed as both an? \\w+ and an? \\w+"):
                mk.cluster_promote(self.BASES, self.placed(), two)
        cl = {"workshops": [self.wk(1, base="0C1AEB:A-B.esm"), self.wk(2, base="0C1AEB:AB.esp")]}
        entries = mk.cluster_promote(self.BASES, self.placed(), cl)[1]["workshops"]
        self.assertEqual(len({e["edid"] for e in entries}), 2)
        self.assertEqual([e["reference_index"] for e in entries], [1, 2])
        from unittest.mock import patch
        with patch.object(mk, "promoted_edid", return_value="ForcedCollision"):
            with self.assertRaisesRegex(ValueError, "two FO4 sources"):
                mk.cluster_promote(self.BASES, self.placed(), cl)

    def test_slot_check_refuses_bad_station_identities(self):
        _cl, objects, good = self.plan()
        W2, B5 = "000003:Fallout4.esm", "000005:Fallout4.esm"
        cases = (
            ("moved", lambda i: i["workshops"][W2].update(ref="000805") or i["benches"][B5].update(ref="000804")
             or i["workshops"]["000002:Fallout4.esm"].update(ref="000807")),
            ("workshop base overlaps", lambda i: [v.update(base="000809") for v in i["workshops"].values()]),
            ("another promoted class", lambda i: [v.update(base="00080D") for v in i["workshops"].values()]),   # the activators' ACTI
            ("two bases", lambda i: i["workshops"][W2].update(base="000811")),
            ("not its vanilla", lambda i: i["benches"][B5].update(base="2B6A62:Starfield.esm")),
            ("not its vanilla", lambda i: i["benches"][B5].update(kind="armor")),
            ("differs from objects", lambda i: i.pop("benches")),
            ("differs from objects", lambda i: i["workshops"].pop(W2)),
            ("missing or invalid", lambda i: i["benches"][B5].pop("base")),
        )
        for why, change in cases:
            ids = json.loads(json.dumps(good))
            change(ids)
            with self.assertRaisesRegex(ValueError, why, msg=why):
                mk.check_reference_slots(objects, ids)
        two = json.loads(json.dumps(objects))                     # a bench whose cluster entry names another kind's vanilla
        two["benches"][0]["vanilla"] = "2B6A62:Starfield.esm"
        with self.assertRaisesRegex(ValueError, "not the weapon bench"):
            mk.check_reference_slots(two, good)

    def records(self, objects, ids, own=0x01000000, **override):
        """Raw records the writer would give for plan(): the station records in full, the rest as the counts need."""
        def z(text):
            return text.encode("utf-8") + b"\0"

        def refr(e, v):
            base = own | int(v["base"], 16) if ":" not in v["base"] else mk.master_fid(v["base"])
            return {"sig": "REFR", "fid": own | int(v["ref"], 16), "flags": 0,
                    "fields": [(b"NAME", struct.pack("<I", override.get("bench_base", base) if ":" in v["base"] else base)),
                               (b"DATA", struct.pack("<6f", *e["pos"], *e["rot"]))]}
        c, i, a, t, w = (objects[k][0] for k in ("containers", "items", "activators", "terminals", "workshops"))
        recs = [{"sig": "CONT", "fid": own | 0x80B, "flags": 0, "fields": [(b"EDID", z(c["edid"])), (b"MODL", z(c["model"]))]},
                {"sig": "MISC", "fid": own | 0x80C, "flags": 0, "fields": [(b"EDID", z(i["edid"])), (b"MODL", z(i["model"])), (b"FULL", z(i["name"])), (b"DATA", struct.pack("<if", 1, 0.1))]},
                {"sig": "ACTI", "fid": own | 0x80D, "flags": 0, "fields": [(b"EDID", z(a["edid"])), (b"MODL", z(a["model"])), (b"FULL", z(a["name"]))]},
                {"sig": "TERM", "fid": own | 0x80E, "flags": 0, "fields": [(b"EDID", z(t["edid"])), (b"DNAM", struct.pack("<I", own | 0x80F)), (b"NAM1", b"\x02"), (b"FULL", z(t["name"])), (b"MODL", z(t["model"]))]},
                {"sig": "TMLM", "fid": own | 0x80F, "flags": 0, "fields": [(b"EDID", z(t["menu_edid"])), (b"FULL", z(t["name"])), (b"TMVT", struct.pack("<I", 1)), (b"BSIZ", struct.pack("<I", 1)), (b"BTXT", z(t["body"])), (b"TPLT", b"\0"), (b"ISIZ", struct.pack("<I", 0))]}]
        kwda = override.get("kwda", [0x054BA7, 0x2CFDE6, 0x2BE3B5])
        prps = override.get("prps", [(0x063FC5, w["radius"], 0)])
        wk = {"sig": "ACTI", "fid": own | 0x810, "flags": 0, "fields": [
            (b"EDID", z(w["edid"])), (b"FULL", z(override.get("wk_name", w["name"]))), (b"MODL", z(w["model"])),
            (b"KSIZ", struct.pack("<I", len(kwda))), (b"KWDA", struct.pack(f"<{len(kwda)}I", *kwda)),
            (b"PRPS", b"".join(struct.pack("<IfI", *p) for p in prps))]}
        if override.get("vmad"):
            wk["fields"].insert(1, (b"VMAD", b"\x06\x00\x02\x00\x00\x00"))
        recs.append(wk)
        if override.get("furn"):
            recs.append({"sig": "FURN", "fid": own | 0x811, "flags": 0, "fields": [(b"EDID", z("FO4Core_furn_x"))]})
        for k in ("containers", "items", "activators", "terminals", "workshops", "benches"):
            for e in objects[k]:
                recs.append(refr(e, ids[k][e["src"]]))
        recs += [{"sig": "REFR", "fid": own | 0x812, "flags": 0, "fields": []},
                 {"sig": "REFR", "fid": own | 0x813, "flags": 0, "fields": []}]                # COC marker, anchor
        return recs

    def test_check_counts_and_bindings_of_the_stations(self):
        _cl, objects, ids = self.plan()
        own, exp = 0x01000000, {"objects": {"exported": 9, "skipped": {"no model": 1}}}
        res = mk.promotion_checks(self.records(objects, ids), own, objects, ids, exp)
        self.assertTrue(all(ok for _w, ok in res), res)
        self.assertEqual([w.split(" (")[0] for w, _ok in res][2:],
                         ["1 CONT = 1 distinct containers edids", "1 MISC = 1 distinct items edids",
                          "2 ACTI = 2 distinct activators + workshops edids", "1 TERM = 1 distinct terminals edids",
                          "1 TMLM = 1 distinct terminals menu edids", "0 FURN of our own",
                          "every promoted REFR names its CONT / MISC / ACTI / TERM / FURN"])
        self.assertTrue(res[0][0].endswith("+ 1 containers + 1 items + 1 activators + 1 terminals + 2 workshops + 2 benches"), res[0][0])
        self.assertIn("workshop keyword, radius; bench vanilla base", res[-1][0])
        self.assertIn("2 benches bind to the vanilla FURN of 2 kinds: armor, weapon", res[-2][0])
        for override, why in (({"kwda": [0x2CFDE6, 0x2BE3B5]}, "lacks WorkshopKeyword"),
                              ({"prps": [(0x063FC5, 150.0, 0)]}, "OutpostBuildAreaRadius"),
                              ({"prps": []}, "OutpostBuildAreaRadius"),
                              ({"prps": [(0x063FC5, 250.0, 0), (0x063FC5, 250.0, 0)]}, "OutpostBuildAreaRadius"),
                              ({"vmad": True}, "carries a VMAD"),
                              ({"wk_name": "Decorate"}, "ACTI name"),
                              ({"bench_base": 0x002B6A62}, "REFR names 002B6A62")):
            pp = mk.promoted_record_check(self.records(objects, ids, **override), own, objects, ids)
            self.assertTrue(pp and why in pp[0], (override, pp))
        res = dict((w.split(" (")[0], ok) for w, ok in mk.promotion_checks(self.records(objects, ids, furn=True), own, objects, ids, exp))
        self.assertFalse(res["1 FURN of our own"])                         # a FURN of our own is not this design
        other, other_obj = json.loads(json.dumps(ids)), json.loads(json.dumps(objects))
        other["benches"]["000005:Fallout4.esm"]["base"] = "2B6A63:Fallout4.esm"    # not a master of the plugin
        self.assertIn("objects.json names", mk.promoted_record_check(self.records(objects, ids), own, objects, other)[0])
        other_obj["benches"][0]["vanilla"] = "2B6A63:Fallout4.esm"
        self.assertIn("not a master", mk.promoted_record_check(self.records(objects, ids), own, other_obj, other)[0])

    @staticmethod
    def synthetic_starfield(path, **change):
        """A synthetic Starfield.esm with the station records make_core64c.station_master_check binds to."""
        from test_fo4light import record, group
        tes4 = b"TES4" + struct.pack("<IIIIHH", 0, 0, 0, 0, 131, 0)
        kw = [(0x04AF68, b"MustPersist"), (0x054BA7, change.get("wk_edid", b"WorkshopKeyword")), (0x2CFDE6, b"OutpostCategoryCrafting"),
              (0x2BE3B5, b"OutpostCategoryFurniture"), (0x257536, b"OutpostBlockFlycam")]
        house_kw = [k for k, _e in kw]
        actis = group(b"ACTI", 0, [record(b"ACTI", 0x024DC7, [(b"EDID", b"OutpostPlayerHouseActivator\0"),
                                                               (b"KWDA", struct.pack(f"<{len(house_kw)}I", *house_kw)),
                                                               (b"PRPS", struct.pack("<IfI", 0x063FC5, 250.0, 0))])])
        kywds = group(b"KYWD", 0, [record(b"KYWD", k, [(b"EDID", e + b"\0")]) for k, e in kw])
        avifs = group(b"AVIF", 0, [record(b"AVIF", 0x063FC5, [(b"EDID", b"OutpostBuildAreaRadius\0")])])
        benches = [(0x2B6A63, b"WorkbenchWeapon", 2, 0x2CE1C0), (0x2B6A62, b"WorkbenchArmor", 7, 0x0657FF),
                   (0x2B6A61, b"WorkbenchChem", 5, 0x102158), (0x2B6A65, b"WorkbenchFood", change.get("food_wbdt", 5), 0x102152)]
        furns = group(b"FURN", 0, [record(b"FURN", i, [(b"EDID", e + b"\0"), (b"KWDA", struct.pack("<I", r)), (b"WBDT", bytes([w, 0]))],
                                          compress=(i == 0x2B6A62)) for i, e, w, r in benches])
        with open(path, "wb") as f:
            f.write(tes4 + actis + kywds + avifs + furns)

    def test_station_master_check_against_a_synthetic_starfield(self):
        _cl, objects, ids = self.plan()
        own = 0x01000000
        with tempfile.TemporaryDirectory() as d:
            esm = os.path.join(d, "Starfield.esm")
            self.synthetic_starfield(esm)
            self.assertEqual(mk.station_master_check(esm, self.records(objects, ids), own, objects, ids), [])
            self.assertEqual(mk.station_master_check(esm, [], own, {"refs": []}, {}), [])          # no stations: nothing to check
            # the category keywords must be exactly the template's, in its order, after WorkshopKeyword
            for kwda, why in (([0x054BA7, 0x2BE3B5, 0x2CFDE6], "KWDA"), ([0x054BA7, 0x2CFDE6], "KWDA"),
                              ([0x054BA7, 0x04AF68, 0x2CFDE6, 0x2BE3B5], "KWDA"), ([0x2CFDE6, 0x2BE3B5, 0x054BA7], "KWDA")):
                pp = mk.station_master_check(esm, self.records(objects, ids, kwda=kwda), own, objects, ids)
                self.assertTrue(pp and why in pp[0], (kwda, pp))
            pp = mk.station_master_check(esm, self.records(objects, ids, prps=[(0x063FC5, 250.0, 0), (0x3807C4, 1.0, 0)]), own, objects, ids)
            self.assertIn("not one OutpostBuildAreaRadius", pp[0])
            self.synthetic_starfield(esm, food_wbdt=0)                        # a kind's vanilla bench without a bench type
            cooking = json.loads(json.dumps(objects))
            cooking["benches"][1].update(kind="cooking", vanilla="2B6A65:Starfield.esm")
            cids = json.loads(json.dumps(ids))
            cids["benches"]["000006:Fallout4.esm"].update(base="2B6A65:Starfield.esm", kind="cooking")
            pp = mk.station_master_check(esm, self.records(cooking, cids), own, cooking, cids)
            self.assertEqual(len(pp), 1)
            self.assertIn("cooking: 2B6A65:Starfield.esm (WorkbenchFood) WBDT 0", pp[0])
            self.synthetic_starfield(esm, wk_edid=b"NotTheWorkshopKeyword")
            self.assertIn("not WorkshopKeyword", mk.station_master_check(esm, self.records(objects, ids), own, objects, ids)[0])

    def test_light_identities_skip_a_vanilla_bench_base(self):
        objects = {"lights": [{"src": "L1", "edid": "FO4Core_ligh_a"}], "light_bases": [{"edid": "FO4Core_ligh_a"}]}
        ids = {"bases": {"x": "000800"}, "refs": {"R": "000801"},
               "benches": {"B": {"base": "2B6A63:Starfield.esm", "ref": "000802", "kind": "weapon"}},
               "workshops": {"W": {"base": "000804", "ref": "000803"}},
               "lights": {"L1": {"base": "000806", "ref": "000805"}}}
        mk.check_light_identities(objects, ids)                              # the bench's master base is no id of ours
        ids["lights"]["L1"] = {"base": "000805", "ref": "000804"}
        with self.assertRaises(ValueError):
            mk.check_light_identities(objects, ids)

    def test_formids_diff_sections(self):
        old = {"plugin": "P.esm", "bases": {"a": "000800"}, "refs": {"r1": "000801", "r2": "000802"},
               "containers": {"c1": {"base": "000900", "ref": "000803"}, "w1": {"base": "000901", "ref": "000804"}},
               "navmeshes": ["000A00", "000A01"], "navi": "000FF1:Starfield.esm"}
        new = {"plugin": "P.esm", "bases": {"a": "000800"}, "refs": {"r1": "000801", "r2": "000802"},
               "containers": {"c1": {"base": "000900", "ref": "000803"}},
               "workshops": {"w1": {"base": "000902", "ref": "000804"}},
               "navmeshes": ["000A02", "000A03"], "navi": "000FF1:Starfield.esm"}
        d = mk.formids_diff(old, new)
        self.assertEqual({k: v["status"] for k, v in d.items()},
                         {"plugin": "identical", "bases": "identical", "refs": "identical", "containers": "changed",
                          "workshops": "added", "navmeshes": "shifted", "navi": "identical"})
        self.assertEqual((d["containers"]["same"], d["containers"]["changed"], d["containers"]["only_old"], d["containers"]["only_new"],
                          d["containers"]["only_old_examples"]), (1, 0, 1, 0, ["w1"]))
        self.assertEqual((d["navmeshes"]["by"], d["navmeshes"]["count"], d["refs"]["count"], d["workshops"]["count"]), (2, 2, 2, 1))
        new["navmeshes"] = ["000A02", "000A05"]
        new["containers"]["c1"]["base"] = "000905"
        d = mk.formids_diff(old, new)
        self.assertEqual((d["navmeshes"]["status"], d["containers"]["changed"], d["containers"]["examples"][0]["src"],
                          d["containers"]["ref_kept"]), ("differs", 1, "c1", 1))
        self.assertNotIn("ref_kept", mk.formids_diff({"refs": {"a": "1"}}, {"refs": {"a": "2"}})["refs"])
        with tempfile.TemporaryDirectory() as t:
            for n, v in (("old", old), ("new", new)):
                os.makedirs(os.path.join(t, n))
                with open(os.path.join(t, n, "formids.json"), "w") as f:
                    json.dump(v, f)
            self.assertEqual(mk.cmd_compare_ids(type("A", (), {"out": os.path.join(t, "new"), "against": os.path.join(t, "old")})()), 0)
            with open(os.path.join(t, "new", "formids_diff.json")) as f:
                self.assertEqual(json.load(f)["sections"]["navmeshes"]["status"], "differs")


class DoorPromotionTests(unittest.TestCase):
    """Scripted load doors (docs/terrain/scripted-doors.md): --cluster "doors" become ACTI references in their slot
    with the FO4SF_LoadDoor VMAD and an exterior arrival marker appended after every other record; the identities and
    the raw records are checked."""
    BASES = [{"edid": "FO4Core_a", "model": "fo4core\\a.nif"},
             {"edid": "FO4Core_indmetaldoorload01", "model": "fo4core\\interiors\\industrial\\doors\\indmetaldoorload01.nif"}]

    @staticmethod
    def placed(n=5, disabled=()):
        return [{"src": f"{i + 1:06X}:Fallout4.esm", "base": 1 if i in (1, 3) else 0, "cell": [-5, 6], "pos": [-469.85 + i, 636.71, 42.36],
                 "rot": [0, 0, 2.5812], "scale": 1.0, "disabled": i in disabled} for i in range(n)]

    @staticmethod
    def entry(i=1, **kw):
        e = {"src": f"{i + 1:06X}:Fallout4.esm", "base": "018C8B:Fallout4.esm", "editor_id": "IndMetalDoorLoad01",
             "destination": {"plugin": "FO4Port.esm", "id": "00DEFF", "port_ref": "007D0B", "port_cell": "006C46",
                             "door": "0EE5D6:Fallout4.esm", "flags": 0,
                             "arrival": {"pos": [5.449, 17.291, -3.654], "rot": [0, 0, 4.7124]}},
             "return": {"arrival": {"pos": [-469.444, 636.074, 42.356], "rot": [0, 0, 2.5812]}, "flags": 0}}
        e.update(kw)
        return e

    def test_cluster_doors_entries(self):
        keep, doors = mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry()]})
        self.assertEqual([p["src"] for p in keep], ["000001:Fallout4.esm", "000003:Fallout4.esm", "000004:Fallout4.esm", "000005:Fallout4.esm"])
        d = doors[0]
        self.assertEqual((d["src"], d["reference_index"], d["edid"], d["model"], d["name"]),
                         ("000002:Fallout4.esm", 1, "FO4Core_door_018c8b_fallout4", self.BASES[1]["model"], "Door"))
        self.assertEqual(d["destination"], {"plugin": "FO4Port.esm", "id": 0xDEFF, "ref": "007D0B", "cell": "006C46",
                                            "door": "0EE5D6:Fallout4.esm", "arrival": {"pos": [5.449, 17.291, -3.654], "rot": [0, 0, 4.7124]}})
        self.assertEqual(d["arrival"], {"pos": [-469.444, 636.074, 42.356], "rot": [0, 0, 2.5812], "cell": [-5, 6]})
        self.assertEqual((d["cell"], d["pos"], d["scale"]), ([-5, 6], [-468.85, 636.71, 42.36], 1.0))
        _keep, named = mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(name="Metal Door", destination=dict(
            self.entry()["destination"], id=0x1234))]})
        self.assertEqual((named[0]["name"], named[0]["destination"]["id"]), ("Metal Door", 0x1234))
        mk.door_arrivals_inside(doors, {"cell_min": -32, "cell_max": 31})
        with self.assertRaisesRegex(ValueError, "outside the overlay"):
            mk.door_arrivals_inside(doors, {"cell_min": 0, "cell_max": 31})
        # through cluster_promote with another class: one slot plan, a source in two classes refused
        cl = {"doors": [self.entry()], "activators": [{"src": "000004:Fallout4.esm", "name": "Bell", "base": "0BB1E1:Fallout4.esm"}]}
        keep, promoted = mk.cluster_promote(self.BASES, self.placed(), cl)
        self.assertEqual({k: [e["reference_index"] for e in v] for k, v in promoted.items() if v}, {"doors": [1], "activators": [3]})
        cl["activators"].append({"src": "000002:Fallout4.esm", "name": "Bell", "base": "0BB1E1:Fallout4.esm"})
        with self.assertRaisesRegex(ValueError, "listed as both an activator and a door"):
            mk.cluster_promote(self.BASES, self.placed(), cl)

    def test_cluster_doors_refusals(self):
        def bad(regex, **kw):
            with self.assertRaisesRegex(ValueError, regex):
                mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(**kw)]})
        dest = self.entry()["destination"]
        bad("needs a destination", destination=None)
        bad("plugin file name", destination=dict(dest, plugin="sub\\FO4Port.esm"))
        bad("plugin file name", destination=dict(dest, plugin="notes.txt"))
        bad("plugin file name", destination=dict(dest, plugin=""))
        for v in ("000000", 0, 0x1000000, "GGGGGG", "7", None):
            bad("plugin-local id", destination=dict(dest, id=v))
        bad("destination ref", destination=dict(dest, port_ref="7D0B"))
        bad("destination cell", destination={k: v for k, v in dest.items() if k != "port_cell"})
        bad("arrival needs pos and rot", destination={k: v for k, v in dest.items() if k != "arrival"})
        bad("arrival needs pos and rot", **{"return": {"arrival": {"pos": [1, 2, 3]}}})
        bad("three finite numbers", **{"return": {"arrival": {"pos": [1, 2], "rot": [0, 0, 0]}}})
        bad("three finite numbers", **{"return": {"arrival": {"pos": [1, 2, float("nan")], "rot": [0, 0, 0]}}})
        bad("not one non-empty line", name="two\nlines")
        bad("not placed", src="ABCDEF:Fallout4.esm")
        with self.assertRaisesRegex(ValueError, "disabled"):
            mk.cluster_doors(self.BASES, self.placed(disabled=(1,)), {"doors": [self.entry()]})
        with self.assertRaisesRegex(ValueError, "listed twice"):
            mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(), self.entry()]})
        other = self.entry(3, destination=dict(dest, id="00DF00", port_ref="007D0A"))
        with self.assertRaisesRegex(ValueError, "different name / model"):
            mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(), dict(other, name="Gate")]})
        with self.assertRaisesRegex(ValueError, "share the destination FO4Port.esm:00DEFF"):
            mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(), self.entry(3, destination=dict(dest, port_ref="007D0A"))]})
        with self.assertRaisesRegex(ValueError, "share the interior door"):
            mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(), self.entry(3, destination=dict(dest, id="00DF00"))]})
        _keep, two = mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry(), other]})
        self.assertEqual([e["destination"]["id"] for e in two], [0xDEFF, 0xDF00])

    def ids(self):
        """bases 800..801, slots 802..806 (the door in 803), CONT 807, NAVM 808..809, lights 80A (REFR) + 80B (LIGH),
        then the door's marker 80C and its ACTI 80D."""
        objects = {"refs": [{"src": "R1"}, {"src": "R3"}, {"src": "R5"}], "containers": [{"src": "C1", "reference_index": 3}],
                   "doors": [dict(mk.cluster_doors(self.BASES, self.placed(), {"doors": [self.entry()]})[1][0])],
                   "lights": [{"src": "L1", "edid": "B"}], "light_bases": [{"edid": "B"}]}
        ids = {"bases": {"a": "000800", "b": "000801"}, "refs": {"R1": "000802", "R3": "000804", "R5": "000806"},
               "containers": {"C1": {"base": "000807", "ref": "000805"}},
               "doors": {"000002:Fallout4.esm": {"base": "00080D", "ref": "000803", "arrival": "00080C"}},
               "navmeshes": ["000808", "000809"], "lights": {"L1": {"base": "00080B", "ref": "00080A"}}}
        return objects, ids

    def test_map_markers_after_the_doors_keep_the_identity_checks(self):
        # the PC's full cluster build (#328): formids.json map_marker_refs {world: {tag: id}} is not a promoted class
        objects, ids = self.ids()
        ids["map_markers"] = {"W": "00080E"}
        ids["map_marker_refs"] = {"W": {"RedRocket": "00080E", "Sanctuary": "00080F"}}
        mk.check_reference_slots(objects, ids)
        mk.check_light_identities(objects, ids)
        mk.check_door_identities(objects, ids)
        self.assertNotIn(0x80E, mk.ids_before(ids, mk.APPENDED))

    def test_door_identities_after_the_lights_and_the_slot_kept(self):
        objects, ids = self.ids()
        mk.check_reference_slots(objects, ids)
        mk.check_light_identities(objects, ids)                    # the door's appended ids do not count as "other"
        mk.check_door_identities(objects, ids)
        mk.check_door_identities({"refs": []}, {})                 # no doors: nothing to check
        bad = copy.deepcopy(ids)
        bad["doors"]["000002:Fallout4.esm"]["arrival"] = "00080B"  # before the lights
        with self.assertRaisesRegex(ValueError, "not new id 00080C"):
            mk.check_door_identities(objects, bad)
        bad = copy.deepcopy(ids)
        bad["doors"]["000002:Fallout4.esm"]["base"] = "00080E"     # not right after the markers
        with self.assertRaisesRegex(ValueError, "ACTI"):
            mk.check_door_identities(objects, bad)
        bad = copy.deepcopy(ids)
        bad["doors"]["000002:Fallout4.esm"]["ref"] = "000805"      # another slot
        with self.assertRaisesRegex(ValueError, "moved"):
            mk.check_reference_slots(objects, bad)
        bad = copy.deepcopy(ids)
        bad["doors"]["000002:Fallout4.esm"]["arrival"] = "000806"  # inside the reserved range
        with self.assertRaisesRegex(ValueError, "arrival marker overlaps"):
            mk.check_reference_slots(objects, bad)
        with self.assertRaisesRegex(ValueError, "declared door set"):
            mk.check_door_identities(objects, dict(ids, doors={}))
        self.assertEqual(mk.appended_ids(ids), {0x80C, 0x80D})
        own = 1 << 24
        recs = [{"sig": s, "fid": own | f, "flags": 0, "fields": []} for s, f in
                (("STAT", 0x800), ("REFR", 0x803), ("CONT", 0x807), ("NAVM", 0x809), ("REFR", 0x80A), ("LIGH", 0x80B), ("REFR", 0x80C), ("ACTI", 0x80D))]
        self.assertEqual(mk.lights_after(recs, 1, ids), (0x80A, 0x809))
        self.assertEqual(mk.doors_after(recs, 1, ids), (0x80C, 0x80B))
        recs.append({"sig": "REFR", "fid": own | 0x80E, "flags": 0, "fields": []})   # another record after the doors
        first, last = mk.doors_after(recs, 1, ids)
        self.assertLess(first, last)

    def test_raw_door_records(self):
        objects, ids = self.ids()
        own = 1 << 24
        e = objects["doors"][0]
        inside = e["destination"]["arrival"]["pos"]                # the interior marker: the exterior door's position
        vm = mk.vmad_patch.load_door_vmad("FO4Port.esm", 0xDEFF, inside)
        recs = [{"sig": "ACTI", "fid": own | 0x80D, "flags": 0, "fields": [
                    (b"EDID", b"FO4Core_door_018c8b_fallout4\0"), (b"MODL", e["model"].encode() + b"\0"), (b"FULL", b"Door\0"),
                    (b"PNAM", bytes.fromhex("cc4c3300")), (b"FNAM", b"\0\0"), (b"JNAM", struct.pack("<H", 360))]},
                {"sig": "REFR", "fid": own | 0x803, "flags": 0, "fields": [
                    (b"VMAD", vm), (b"NAME", struct.pack("<I", own | 0x80D)), (b"DATA", struct.pack("<6f", *e["pos"], *e["rot"]))]},
                {"sig": "REFR", "fid": own | 0x80C, "flags": 0x400, "fields": [
                    (b"NAME", struct.pack("<I", mk.XMARKER)), (b"DATA", struct.pack("<6f", *e["arrival"]["pos"], *e["arrival"]["rot"]))]}]
        self.assertEqual(mk.door_record_problems(recs, own, objects, ids), [])
        self.assertEqual(mk.promoted_record_check(recs, own, {"refs": [], "doors": objects["doors"]}, ids), [])
        res = mk.promotion_checks(recs + [{"sig": "REFR", "fid": own | f, "flags": 0, "fields": []} for f in (0x802, 0x804, 0x805, 0x806, 0x7FF)],
                                  own, {"refs": [{"src": "R1"}, {"src": "R3"}, {"src": "R5"}], "doors": objects["doors"]}, ids,
                                  {"objects": {"exported": 4, "skipped": {}}})
        self.assertTrue(all(ok for _w, ok in res), res)
        self.assertIn("+ 1 door arrival markers", res[0][0])
        self.assertIn("1 ACTI = 1 distinct doors edids", res[2][0])

        def broken(change):
            r = copy.deepcopy(recs)
            change(r)
            return mk.door_record_problems(r, own, objects, ids)
        self.assertIn("PNAM", broken(lambda r: r[0]["fields"].__setitem__(3, (b"PNAM", bytes(4))))[0])
        self.assertIn("carries a VMAD", broken(lambda r: r[0]["fields"].append((b"VMAD", vm)))[0])
        self.assertIn("REFR VMAD", broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", mk.vmad_patch.load_door_vmad("FO4Port.esm", 0xDF00, inside))))[0])
        # the destination position: missing (the two-property door of #272), another point, an axis swapped
        self.assertIn("REFR VMAD", broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", mk.vmad_patch.load_door_vmad("FO4Port.esm", 0xDEFF))))[0])
        self.assertIn("REFR VMAD", broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", mk.vmad_patch.load_door_vmad(
            "FO4Port.esm", 0xDEFF, [inside[0], inside[1], inside[2] + 0.01]))))[0])
        self.assertIn("REFR VMAD", broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", mk.vmad_patch.load_door_vmad(
            "FO4Port.esm", 0xDEFF, [inside[1], inside[0], inside[2]]))))[0])
        self.assertEqual(broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", mk.vmad_patch.load_door_vmad(
            "FO4Port.esm", 0xDEFF, [inside[0] + 4e-4, inside[1], inside[2]])))), [])          # float32 rounding is tolerated
        # the six-property shape: the bool UseDestinationPosition must be there and true whenever the floats are
        props = mk.vmad_patch.load_door_scripts("FO4Port.esm", 0xDEFF, inside)[0]["properties"]
        self.assertEqual([p["name"] for p in props][2:], ["DestinationX", "DestinationY", "DestinationZ", "UseDestinationPosition"])
        self.assertEqual(vm, mk.vmad_patch.encode([{"name": "FO4SF_LoadDoor", "status": 0, "properties": props}]))

        def with_props(kept):
            blob = mk.vmad_patch.encode([{"name": "FO4SF_LoadDoor", "status": 0, "properties": kept}])
            return broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", blob)))
        self.assertEqual(with_props(props), [])
        self.assertEqual(with_props(props[:2] + [props[5]] + props[2:5]), [])             # the script's declaration order
        for kept in (props[:5],                                                           # floats, no bool: the old writer
                     props[:5] + [dict(props[5], value=False)],                           # the bool false
                     props[:2] + [props[5]],                                              # the bool without the floats
                     props[:2] + [dict(props[5], value=False)] + props[2:5],
                     props[:5] + [dict(props[5], type=3, value=1)]):                      # the bool an int
            self.assertIn("REFR VMAD", with_props(kept)[0])
        self.assertIn("without UseDestinationPosition", with_props(props[:5])[0])
        self.assertIn("REFR VMAD", broken(lambda r: r[1]["fields"].__setitem__(0, (b"VMAD", vm + b"\0")))[0])
        self.assertIn("REFR VMAD", broken(lambda r: r[1]["fields"].pop(0))[0])
        self.assertIn("VMAD not first", broken(lambda r: r[1]["fields"].reverse())[0])
        self.assertIn("not XMarker", broken(lambda r: r[2]["fields"].__setitem__(0, (b"NAME", struct.pack("<I", own | 0x800))))[0])
        self.assertIn("position / rotation", broken(lambda r: r[2]["fields"].append((b"XSCL", struct.pack("<f", 2.0))))[0])
        self.assertIn("flags", broken(lambda r: r[2].__setitem__("flags", 0))[0])          # temporary: no longer the door's marker
        self.assertIn("flags", broken(lambda r: r[2].__setitem__("flags", 0xC00))[0])      # persistent but initially disabled
        self.assertIn("no arrival marker", broken(lambda r: r.pop(2))[0])
        self.assertIn("not declared", mk.door_record_problems(recs, own, objects, {"doors": {}})[0])

    def test_marker_groups_and_placement(self):
        """door_marker_groups reads where a REFR sits (raw group walk); door_marker_placement wants every arrival marker
        in the persistent children of the world's persistent cell, the anchor's, not in an exterior cell."""
        vp = mk.vmad_patch
        own = 1 << 24

        def ref(fid, flags):
            return vp.record_bytes(b"REFR", own | fid, flags, [(b"NAME", struct.pack("<I", mk.XMARKER)),
                                                                (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0))])

        def children(cell, groups):
            return vp.Group(struct.pack("<I", own | cell), 6, bytes(8),
                            [vp.Group(struct.pack("<I", own | cell), t, bytes(8), refs) for t, refs in groups])
        wrld = vp.record_bytes(b"WRLD", own | 0x803, 0, [(b"EDID", b"W\0")])
        pcell = vp.record_bytes(b"CELL", own | 0x900, 0x400, [(b"DATA", b"\0\0")])
        xcell = vp.record_bytes(b"CELL", own | 0x901, 0, [(b"XCLC", struct.pack("<iiI", 1, 2, 0))])
        block = vp.Group(struct.pack("<hh", 0, 0), 4, bytes(8), [vp.Group(struct.pack("<hh", 0, 0), 5, bytes(8), [
            xcell, children(0x901, [(8, [ref(0x80E, 0x400)]), (9, [ref(0x80D, 0)])])])])
        world = vp.Group(struct.pack("<I", own | 0x803), 1, bytes(8),
                         [pcell, children(0x900, [(8, [ref(0x800, 0x400), ref(0x80C, 0x400)]), (9, [ref(0x80F, 0)])]), block])
        top = vp.Group(b"WRLD", 0, bytes(8), [wrld, world])
        tes4 = vp.record_bytes(b"TES4", 0, 1, [(b"HEDR", struct.pack("<fII", 0.96, 9, 0x910)), (b"MAST", b"Starfield.esm\0")])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "Synthetic.esm")
            with open(path, "wb") as f:
                f.write(tes4.serialize() + top.serialize())
            fids = {own | f for f in (0x800, 0x80C, 0x80D, 0x80E, 0x80F)}
            where = mk.door_marker_groups(path, fids)
        self.assertEqual(where[own | 0x80C], {"cell": own | 0x900, "grid": None, "group": 8})
        self.assertEqual(where[own | 0x80D], {"cell": own | 0x901, "grid": (1, 2), "group": 9})
        self.assertEqual(where[own | 0x80E], {"cell": own | 0x901, "grid": (1, 2), "group": 8})
        self.assertEqual(mk.door_marker_placement(where, [own | 0x80C], own | 0x800), [])
        self.assertIn("marker 0100080E", mk.door_marker_placement(where, [own | 0x80E], own | 0x800)[0])  # an exterior cell's persistent group
        self.assertIn("marker 0100080D", mk.door_marker_placement(where, [own | 0x80D], own | 0x800)[0])  # temporary in an exterior cell
        self.assertIn("marker 0100080F", mk.door_marker_placement(where, [own | 0x80F], own | 0x800)[0])  # temporary in the persistent cell
        self.assertIn("marker 01000811", mk.door_marker_placement(where, [own | 0x811], own | 0x800)[0])  # not written
        self.assertIn("the anchor", mk.door_marker_placement(where, [own | 0x80C], own | 0x80D)[0])       # the anchor in an exterior cell

