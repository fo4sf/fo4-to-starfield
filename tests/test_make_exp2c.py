"""Terrain experiment 2c builder (scripts/terrain/make_exp2c.py): point classification, object choice, raw plugin walk
and dependency check, all on synthetic data (no game files)."""
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
spec = importlib.util.spec_from_file_location("make_exp2c", root / "scripts" / "terrain" / "make_exp2c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
from fo4sf import exterior, nif, sfnif  # noqa: E402


def box_tris(x0, y0, z0, x1, y1, z1):
    c = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [t for q in quads for t in ((c[q[0]], c[q[1]], c[q[2]]), (c[q[0]], c[q[2]], c[q[3]]))]


def fake_world(objects, ground=0.0):
    """A World over a flat 1 x 1-cell BTD (x, y 0..99 m) with box objects: [(src, model, collision, box, rot)]."""
    w = mk.World.__new__(mk.World)
    w.bases, w.placed, tris, owners = [], [], [], []
    for k, (src, model, collision, box, rot) in enumerate(objects):
        w.bases.append({"edid": "FO4CW_" + src.lower(), "model": model, "collision": collision})
        w.placed.append({"src": src, "base": k, "pos": [0.0, 0.0, 0.0], "rot": list(rot), "scale": 1.0,
                         "disabled": False})
        t = box_tris(*box)
        tris += t
        owners += [k] * len(t)
    w.tris, w.owners = np.array(tris, np.float64).reshape(-1, 3, 3), np.array(owners, np.int64)
    w.index = exterior.SurfaceIndex(w.tris, w.owners)
    w.n, w.heights, w.origin, w.step = 1, np.full((128, 128), ground), 0.0, 0.004
    w.by_src = {p["src"]: k for k, p in enumerate(w.placed)}
    return w


class PointTests(unittest.TestCase):
    def test_terrain_points_classified(self):
        w = fake_world([("SLAB", "fo4cw\\a.nif", "fo4-native", (10, 10, -0.5, 20, 20, 0.3), (0, 0, 0)),
                        ("CRATE", "fo4cw\\b.nif", "fo4-native", (30.4, 29, 0, 31, 31, 1.0), (0, 0, 0))])
        pts = [{"label": "on_slab", "x": 15, "y": 15, "expect": 0.0},
               {"label": "by_crate", "x": 30, "y": 30, "expect": 0.0},
               {"label": "clear", "x": 50, "y": 50, "expect": 0.0}]
        out = {p["label"]: p for p in mk.terrain_points(w, pts, 150)}
        self.assertEqual(out["on_slab"]["kind"], "terrain_covered")
        self.assertAlmostEqual(out["on_slab"]["expect"], 0.3)
        self.assertEqual(out["on_slab"]["terrain_expect"], 0.0)
        self.assertEqual(out["on_slab"]["owner"]["src"], "SLAB")
        self.assertEqual(out["by_crate"]["kind"], "terrain_near_object")
        self.assertEqual(out["by_crate"]["expect"], 0.0)
        self.assertEqual(out["by_crate"]["nearby_object"]["distance"], 0.45)
        self.assertEqual(out["clear"]["kind"], "terrain")
        self.assertIsNone(out["clear"]["nearby_object"])

    def test_large_flat_objects_choice(self):
        w = fake_world([
            ("ROOF", "fo4cw\\bld.nif", "fo4-native", (10, 10, 0, 22, 22, 6), (0, 0, 0)),          # elevated, biggest
            ("ROAD1", "fo4cw\\road.nif", "fo4-native", (30, 10, -0.5, 45, 20, 0.2), (0, 0, 0)),
            ("ROAD2", "fo4cw\\road.nif", "fo4-native", (50, 10, -0.5, 66, 20, 0.2), (0, 0, 0)),   # same model: skipped
            ("WALK", "fo4cw\\walk.nif", "fo4-native", (30, 30, -0.5, 40, 36, 0.3), (0, 0, 0)),
            ("SCOL", "fo4cw\\scol\\cm1.nif", "fo4-native", (50, 30, -0.5, 70, 50, 0.2), (0, 0, 0)),  # precombine
            ("GUESS", "fo4cw\\g.nif", "guessed-boxes", (10, 60, -0.5, 30, 80, 0.2), (0, 0, 0)),
            ("TILT", "fo4cw\\t.nif", "fo4-native", (40, 60, -0.5, 60, 80, 0.2), (0.1, 0, 0)),
            ("SMALL", "fo4cw\\s.nif", "fo4-native", (80, 80, 0, 81, 81, 0.5), (0, 0, 0))])
        chosen = mk.large_flat_objects(w, exclude=set())
        self.assertEqual([p["owner"]["src"] for p in chosen], ["ROAD2", "ROOF", "WALK"])
        self.assertEqual([p["label"] for p in chosen], ["flat_road2", "roof_roof", "flat_walk"])
        self.assertAlmostEqual(chosen[1]["expect"], 6.0)
        self.assertAlmostEqual(chosen[1]["above_terrain"], 6.0)
        self.assertEqual(mk.large_flat_objects(w, exclude={"ROOF"}, count_ground=1)[0]["owner"]["src"], "ROAD2")

    def test_collision_kind(self):
        self.assertEqual(mk.collision_kind({"door": {}, "collision_report": {}}), "rigged-door-box")
        self.assertEqual(mk.collision_kind({"collision_report": {"source": "fo4-native"}}), "fo4-native")
        self.assertEqual(mk.collision_kind({"collision_report": {"boxes": 4}}), "guessed-boxes")
        self.assertEqual(mk.collision_kind({"collision_report": {}}), "none")


# ------------------------------------------------------------------------------------------------ synthetic plugin
def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def rec(sig, fid, fields, flags=0):
    body = b"".join(fields)
    return sig + struct.pack("<III", len(body), flags, fid) + bytes(8) + body


def grup(label, gtype, content):
    return b"GRUP" + struct.pack("<I", 24 + len(content)) + label + struct.pack("<i", gtype) + bytes(8) + content


def refr(fid, base, pos, rot=(0, 0, 0), flags=0):
    return rec(b"REFR", fid, [sub(b"NAME", struct.pack("<I", base)), sub(b"DATA", struct.pack("<6f", *pos, *rot))], flags)


def plugin(refs_a, flags_b=0):
    tes4 = rec(b"TES4", 0, [sub(b"HEDR", bytes(12)), sub(b"MAST", b"Starfield.esm\0"), sub(b"DATA", bytes(8))])
    stat = grup(b"STAT", 0, rec(b"STAT", 0x01000B00, [sub(b"EDID", b"FO4CW_x\0"), sub(b"MODL", b"fo4cw\\x.nif\0")]))
    top = rec(b"CELL", 0x01000900, [sub(b"DATA", b"\0\0")])
    top_kids = grup(struct.pack("<I", 0x01000900), 6, grup(struct.pack("<I", 0x01000900), 8,
                                                          refr(0x01000800, 0x3B, (1, 2, 3), flags=0x400)))
    cell = rec(b"CELL", 0x01000901, [sub(b"XCLC", struct.pack("<ii", -1, 2) + bytes(4))])
    temp = refs_a + refr(0x01000A01, 0x01000B00, (4.0, 5.0, 6.0), (0, 0, 1.5), flags_b)
    kids = grup(struct.pack("<I", 0x01000901), 6, grup(struct.pack("<I", 0x01000901), 9, temp))
    blocks = grup(struct.pack("<hh", 0, -1), 4, grup(struct.pack("<hh", -1, 0), 5, cell + kids))
    world = grup(b"WRLD", 0, rec(b"WRLD", 0x01000802, [sub(b"EDID", b"W\0")]) +
                 grup(struct.pack("<I", 0x01000802), 1, top + top_kids + blocks))
    return tes4 + stat + world


class PluginWalkTests(unittest.TestCase):
    def objects(self):
        return ({"bases": [{"edid": "FO4CW_x"}],
                 "refs": [{"src": "A", "base": 0, "cell": [-1, 2], "pos": [-150.5, 250.25, 100.0], "rot": [0, 0, 0],
                           "scale": 1.0, "disabled": False},
                          {"src": "B", "base": 0, "cell": [-1, 2], "pos": [4.0, 5.0, 6.0], "rot": [0, 0, 1.5],
                           "scale": 1.0, "disabled": False}]},
                {"bases": {"FO4CW_x": "000B00"}, "refs": {"A": "000A00", "B": "000A01"}})

    def walk(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "t.esm")
            Path(p).write_bytes(data)
            return mk.overlay_records.walk_plugin(p), mk.walk_cells(p)

    def test_cells_and_refs_match(self):
        good = refr(0x01000A00, 0x01000B00, (-150.5, 250.25, 100.0))
        walked, cells = self.walk(plugin(good))
        self.assertEqual(walked["masters"], ["Starfield.esm"])
        self.assertEqual(cells[0x01000901], {"grid": (-1, 2), "refs": [0x01000A00, 0x01000A01]})
        self.assertEqual(cells[0x01000900], {"grid": None, "refs": [0x01000800]})
        objects, ids = self.objects()
        problems, worst_pos, worst_rot = mk.ref_record_check(walked["records"], 0x01000000, objects, ids)
        self.assertEqual(problems, [])
        self.assertLess(worst_pos, 1e-4)
        self.assertLess(worst_rot, 1e-6)

    def test_mismatches_are_reported(self):
        moved = refr(0x01000A00, 0x01000B00, (-150.5, 250.25, 101.0))
        walked, _ = self.walk(plugin(moved, flags_b=0x800))
        objects, ids = self.objects()
        problems, worst_pos, _ = mk.ref_record_check(walked["records"], 0x01000000, objects, ids)
        self.assertAlmostEqual(worst_pos, 1.0)
        self.assertEqual(problems, ["B: disabled flag"])
        ids["refs"]["A"] = "000A05"
        problems, _, _ = mk.ref_record_check(walked["records"], 0x01000000, objects, ids)
        self.assertIn("A: no REFR 01000A05", problems)


class DependencyTests(unittest.TestCase):
    def test_meshes_materials_and_textures(self):
        with tempfile.TemporaryDirectory() as data:
            shape = sfnif.StaticShape(b"S", b"aa\\bb", 3, 3, "materials\\fo4cw\\m.mat", (0, 0, 0, 1), (0, 0, 0, 1, 1, 1))
            f = sfnif.build_static_nif(b"X", [shape])
            os.makedirs(os.path.join(data, "meshes", "fo4cw"))
            Path(data, "meshes", "fo4cw", "x.nif").write_bytes(nif.serialize(f))
            os.makedirs(os.path.join(data, "materials", "fo4cw"))
            mat = {"Objects": [{"Components": [{"Data": {"File": "Data\\textures\\fo4cw\\x_color.dds"}},
                                               {"Data": {"File": "Data\\Textures\\common\\vanilla.DDS"}}]}]}
            Path(data, "materials", "fo4cw", "m.mat").write_text(json.dumps(mat))
            res = mk.dependency_check(data, ["fo4cw\\x.nif"], vanilla={"textures/common/vanilla.dds"})
            self.assertEqual(sorted(res["missing"]), ["geometries\\aa\\bb.mesh", "textures\\fo4cw\\x_color.dds"])
            os.makedirs(os.path.join(data, "geometries", "aa"))
            Path(data, "geometries", "aa", "bb.mesh").write_bytes(b"m")
            os.makedirs(os.path.join(data, "textures", "fo4cw"))
            Path(data, "textures", "fo4cw", "x_color.dds").write_bytes(b"d")
            res = mk.dependency_check(data, ["fo4cw\\x.nif"], vanilla={"textures/common/vanilla.dds"})
            self.assertEqual(res["missing"], [])
            self.assertEqual(res["counts"]["meshes"], 1)
            self.assertEqual((res["counts"]["textures_own"], res["counts"]["textures_vanilla"]), (1, 1))
            self.assertEqual(mk.dependency_check(data, ["fo4cw\\x.nif"], vanilla=set())["missing"],
                             ["textures\\common\\vanilla.dds"])
            self.assertEqual(mk.dependency_check(data, ["fo4cw\\x.nif"])["counts"]["vanilla_unverified"], 1)


if __name__ == "__main__":
    unittest.main()
