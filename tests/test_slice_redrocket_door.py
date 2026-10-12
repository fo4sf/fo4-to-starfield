"""scripts/slice/make_redrocket_door.py on synthetic data: the Fallout 4 -> Starfield door placement, the link checks,
exp2d's double-placement check, the plan entry (through the runner's own door_test), the raw override compare and the
walk / start / last-try geometry."""
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "slice"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import make_redrocket_door as m  # noqa: E402
import testqueue as tq  # noqa: E402


def ref(fid, where, cell, pos, rot, scale, door, xpos, xrot, flags=0, persistent=True, base="01ED77"):
    return {"formid": fid, "where": where, "cell_editor_id": cell, "persistent_group": persistent, "base": base,
            "pos": pos, "rot": rot, "scale": scale,
            "xtel": {"door": door, "pos": xpos, "rot": xrot, "flags": flags, "transition_interior": None}}


INNER = ref("05E844", "interior", "RedRocket01", [-116.13465, 169.1064, 0], [0, 0, 5.759587], 0.93, "08EB65",
            [-69687.12, 77290, 6984], [0, 0, -3.1081858])
OUTER = ref("08EB65", "Commonwealth persistent cell", None, [-69646.37, 77664.305, 6907.905], [0, 0, 0.24999945],
            0.23, "05E844", [3.4483528, -463.53928, -0.43591836], [0, 0, 2.7014012])


class PlacementTests(unittest.TestCase):
    def test_fallout4_to_starfield(self):
        s = m.side(OUTER, "Ext")
        self.assertEqual(s["pos"], [-994.94814, 1109.49007, 98.68436])
        self.assertEqual(s["rot"], [0.0, 0.0, 0.24999945])
        self.assertEqual(s["scale"], 0.23)
        self.assertEqual(s["xtel"], {"pos": [0.04926, -6.62199, -0.00623], "rot": [0.0, 0.0, 2.7014012], "flags": 0})
        self.assertEqual(s["src"], "08EB65:Fallout4.esm")
        self.assertEqual(m.side(dict(INNER, scale=None), "Int")["scale"], 1.0)

    def test_unsupported_xtels_are_refused(self):
        for bad in ({"transition_interior": "0ABCDE"}, {"flags": 8}):
            with self.assertRaises(ValueError):
                m.side(dict(INNER, xtel=dict(INNER["xtel"], **bad)), "x")
        with self.assertRaises(ValueError):
            m.side(dict(INNER, xtel=None), "x")

    def test_the_link_must_hold_both_ways(self):
        doc = {"refs": [INNER, OUTER]}
        self.assertEqual(m.link_pair(doc), (INNER, OUTER))
        for bad in ({"refs": [INNER]}, {"refs": [INNER, dict(OUTER, xtel=dict(OUTER["xtel"], door="000001"))]},
                    {"refs": [dict(INNER, cell_editor_id="Vault111Cryo"), OUTER]},
                    {"refs": [INNER, dict(OUTER, where="Commonwealth exterior")]},
                    {"refs": [INNER, dict(OUTER, persistent_group=False)]},
                    {"refs": [INNER, dict(OUTER, base="000ABC")]}):
            with self.assertRaises(ValueError):
                m.link_pair(bad)

    def test_double_placement(self):
        objects = {"refs": [{"src": "000001:Fallout4.esm"}]}
        skipped = {"refs": [{"formkey": "08EB65:Fallout4.esm", "reason": "editor_marker", "detail": "marker"}]}
        self.assertEqual(m.double_placement(objects, skipped, "08EB65:Fallout4.esm"), ("skipped", "editor_marker", "marker"))
        self.assertEqual(m.double_placement({"refs": [{"src": "08EB65:Fallout4.esm"}]}, skipped, "08EB65:Fallout4.esm")[0],
                         "placed")
        self.assertEqual(m.double_placement(objects, {"refs": []}, "08EB65:Fallout4.esm")[0], "absent")

    def test_plan_entry_is_a_runner_test(self):
        o = {"start": [-995.53, 1104.14, 99.78], "door": [-994.95, 1109.49, 98.68], "arrival": [-995.53, 1104.14, 99.77],
             "near": [-995.06, 1108.5, 98.31], "ground": 99.73}
        i = {"start": [-6.08, 1.58, 0.06], "door": [-1.66, 2.42, 0.0], "arrival": [0.05, -6.62, -0.01],
             "near": [-2.15, 1.0, -0.01], "floor": 0.24}
        e = m.plan_entry({"outside": o, "inside": i}, "coc FO4CW_RedRocketSpawn", [-989.0286, 1147.2, 105.2609])
        t = tq.door_test(0, e)
        self.assertEqual((t["kind"], t["save"], t["inside"]["cell"]), ("door_trip", m.SAVE, m.PORT_CELL))
        self.assertEqual(t["heading_out"], m.heading(o["start"], o["door"]))
        self.assertEqual(t["heading_in"], m.heading(i["start"], i["door"]))
        self.assertEqual(m.heading([0, 0, 0], [1, 0, 0]), 90.0)
        self.assertEqual(t["outside"]["ref"], m.OUTSIDE_REF)                # the runner's getpos diagnostic
        self.assertEqual((t["moved_m"], t["activate_m"]), (30.0, m.ACTIVATE_M))


def plugin(records, masters=("Starfield.esm",)):
    """A minimal TES4 file: header with masters, then one top group holding the given records [(type, flags, formid,
    data)]; a record with flag 0x40000 is stored zlib-compressed."""
    hdr = b"".join(b"MAST" + struct.pack("<H", len(x) + 1) + x.encode() + b"\0" for x in masters)
    out = b"TES4" + struct.pack("<IIIIHH", len(hdr), 1, 0, 0, 0, 0) + hdr
    body = b""
    for typ, flags, fid, data in records:
        if flags & 0x40000:
            data = struct.pack("<I", len(data)) + zlib.compress(data)
        body += typ + struct.pack("<IIIIHH", len(data), flags, fid, 0, 0, 0) + data
    return out + b"GRUP" + struct.pack("<I", 24 + len(body)) + b"WRLD" + struct.pack("<III", 0, 0, 0) + body


class RawRecordTests(unittest.TestCase):
    def write(self, data):
        f = os.path.join(tempfile.mkdtemp(), "p.esm")
        with open(f, "wb") as h:
            h.write(data)
        return f

    def test_records_and_override_compare(self):
        data = b"EDID\x05\0Cell\0XCLL\x08\0" + struct.pack("<II", 0x01000B4E, 0x0000003B)
        master = m.records(self.write(plugin([(b"CELL", 0x400, 0x01000B4E, data)])))
        self.assertEqual(master[0x01000B4E], ("CELL", 0x400, data))
        packed = m.records(self.write(plugin([(b"CELL", 0x40400, 0x01000B4E, data)])))
        self.assertEqual(packed[0x01000B4E], ("CELL", 0x400, data))          # decompressed, compression flag dropped
        self.assertEqual(m.compare_override(master[0x01000B4E], packed[0x01000B4E], 1, 1), "identical")
        moved = data.replace(struct.pack("<I", 0x01000B4E), struct.pack("<I", 0x02000B4E))
        self.assertEqual(m.compare_override(("CELL", 0x400, data), ("CELL", 0x400, moved), 1, 2), "formid bytes only")
        self.assertIn("byte", m.compare_override(("CELL", 0x400, data), ("CELL", 0x400, data[:-1] + b"\x3c"), 1, 1))
        self.assertIn("size", m.compare_override(("CELL", 0x400, data), ("CELL", 0x400, data + b"\0"), 1, 1))
        self.assertIn("flags", m.compare_override(("CELL", 0x400, data), ("CELL", 0x0, data), 1, 1))


class GeometryTests(unittest.TestCase):
    """A flat floor at z 0 with a 1 m high wall across x = 2 (y < 1) and the door at (6, 0, 0.5)."""
    def support(self, x, y, below):
        top = 1.0 if (1.9 <= x <= 2.1 and y < 1.0) else 0.0
        if top <= below:
            return top, "wall" if top else "floor"
        return (0.0, "floor") if below >= 0 else None

    def blocked(self, x, y, z):
        return ["wall"] if (1.6 <= x <= 2.4 and y < 1.35 and z < 1.0) else []

    def test_walk_profile_follows_the_floor_and_finds_the_wall(self):
        w = m.walk_profile(self.support, [0, 0, 0], [6, 0, 0.5], 0.0, blocked=self.blocked)
        self.assertEqual(w["gaps"], 0)
        self.assertEqual(w["max_rise"], 0.0)                     # a 1 m wall is not climbed (CLIMB 0.3)
        self.assertEqual(w["blocked"]["distance"], 1.75)
        self.assertEqual(w["blocked"]["by"], ["wall"])
        self.assertFalse(m.clear_until_range(w, [6, 0, 0.5], [0, 0, 0]))
        open_walk = m.walk_profile(self.support, [0, 3, 0], [6, 0, 0.5], 0.0, blocked=self.blocked)
        self.assertTrue(m.clear_until_range(open_walk, [6, 0, 0.5], [0, 3, 0]))

    def test_start_is_the_arrival_when_its_walk_is_clear_else_a_clear_spot(self):
        start, walk, how, reach = m.pick_start(self.support, self.blocked, [6, 0, 0.5], [6, 6, 0])
        self.assertEqual((start, how, reach), ([6, 6, 0.05], "arrival", {"to": "marker", "m": 0.5}))  # to the door
        start, walk, how, reach = m.pick_start(self.support, self.blocked, [6, 0, 0.5], [-1, 0, 0])
        self.assertTrue(how.startswith("clear spot"), how)
        self.assertEqual(reach, {"to": "marker", "m": 0.5})
        self.assertTrue(m.clear_until_range(walk, [6, 0, 0.5], start, 0.5, m.MARKER_H))
        self.assertGreaterEqual(m.math.dist(start, [6, 0, 0.5]), m.ACTIVATE_M + 1.5 - 0.1)

    def test_a_walk_clear_only_into_the_range_is_the_second_choice(self):
        # a ring of rock 0.8 to 1.2 m around the door: no straight walk reaches the door itself, every one reaches 2.7 m
        def ring(x, y, z):
            return ["rock"] if 0.8 < m.math.hypot(x - 6, y) < 1.2 else []
        start, walk, how, reach = m.pick_start(self.support, ring, [6, 0, 0.5], [6, 6, 0])
        self.assertEqual((how, reach), ("arrival", {"to": "origin", "m": m.ACTIVATE_M - 0.3}))
        self.assertFalse(m.clear_until_range(walk, [6, 0, 0.5], start, 0.5, m.MARKER_H))
        self.assertTrue(m.clear_until_range(walk, [6, 0, 0.5], start, m.ACTIVATE_M - 0.3))
        self.assertEqual(m.pick_start(self.support, lambda x, y, z: ["rock"], [6, 0, 0.5], [6, 6, 0])[2:],
                         ("arrival (no clear straight walk found)", None))

    def test_door_gap(self):
        door = [0.0, 0.0, 1.0]                            # a marker 1 m above the floor, 0.63 m high (scale 0.23)
        self.assertAlmostEqual(m.door_gap(0.4, 0.3, 0.0, door, 0.63), 0.5)          # overlapping in height: flat
        self.assertAlmostEqual(m.door_gap(0.0, 0.0, -1.0, door, 0.63), 0.2)         # head 0.2 m below the marker
        self.assertAlmostEqual(m.door_gap(0.0, 0.0, 2.0, door, 0.63), 0.37)         # feet above its top

    def test_the_start_keeps_out_of_the_door_range_however_it_is_measured(self):
        self.assertEqual(m.start_min_m(0.93), 5.27)      # RedRocket01's door: 3.57 + 0.85 marker + 0.35 capsule + 0.5
        self.assertEqual(m.start_min_m(0.23), 4.63)      # the exterior door
        # an arrival 3 m from the door is too close for the start: a clear spot at least start_min_m away
        start, walk, how, reach = m.pick_start(self.support, self.blocked, [6, 0, 0.5], [6, 3, 0],
                                               min_m=m.start_min_m(1.0))
        self.assertTrue(how.startswith("clear spot"), how)
        self.assertGreaterEqual(m.math.dist(start, [6, 0, 0.5]), m.start_min_m(1.0))

    def test_near_spot_in_front_of_the_door(self):
        n = m.pick_near(self.support, self.blocked, [6, 0, 0.5], [0, 0, 0], 0.0)
        self.assertEqual((n["distance"], n["angle"], n["pos"]), (1.0, 0, [5.0, 0.0, 0.05]))
        # the straight spot blocked: the next angle
        n = m.pick_near(self.support, lambda x, y, z: ["rock"] if x < 5.5 and abs(y) < 0.3 else [], [6, 0, 0.5],
                        [0, 0, 0], 0.0)
        self.assertEqual((n["distance"], n["angle"]), (1.0, 30))
        self.assertIsNone(m.pick_near(self.support, lambda x, y, z: ["rock"], [6, 0, 0.5], [0, 0, 0], 0.0))


if __name__ == "__main__":
    unittest.main()
