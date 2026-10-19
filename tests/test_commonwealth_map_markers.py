"""Commonwealth map markers (docs/terrain/map-markers.md): the stage entries (src/fo4sf/map_markers.overlay_markers)
and make_core64c check's judgement of the written MapMarker REFRs, LCSR and LCID, on synthetic records only."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "scripts" / "terrain"))
spec = importlib.util.spec_from_file_location("make_core64c", root / "scripts" / "terrain" / "make_core64c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
from fo4sf import map_markers  # noqa: E402

OWN = 0x01000000
SPAWN = [-989.257, 1146.514, 107.143]
BOUNDS = (-3200.0, 3200.0)


def z(s):
    return s.encode() + b"\0"


class OverlayMarkers(unittest.TestCase):
    def markers(self, **kw):
        return map_markers.overlay_markers(SPAWN, BOUNDS, lambda x, y: 0.5 * x / 100.0, **kw)

    def test_four_markers_red_rocket_on_the_coc(self):
        ms = self.markers()
        self.assertEqual([m["tag"] for m in ms], ["RedRocket", "Sanctuary", "Vault111", "Concord"])
        self.assertEqual(ms[0]["pos"], SPAWN)
        self.assertEqual(ms[0]["cell"], [-10, 11])                    # the COC cell FO4Core_RedRocketSpawn

    def test_fo4_position_over_70_on_the_ground(self):
        s = self.markers()[1]
        x, y = -80768.19 / 70, 88174.80 / 70
        self.assertAlmostEqual(s["pos"][0], x, places=3)
        self.assertAlmostEqual(s["pos"][1], y, places=3)
        self.assertAlmostEqual(s["pos"][2], 0.5 * x / 100.0, places=3)
        self.assertEqual(s["cell"], [-12, 12])
        self.assertEqual(s["src"], "072A48:Fallout4.esm")

    def test_marker_outside_the_overlay_is_refused(self):
        with self.assertRaises(ValueError):
            map_markers.overlay_markers(SPAWN, (-1000.0, 1000.0), lambda x, y: 0.0)

    def test_repeated_tag_is_refused(self):
        dup = map_markers.COMMONWEALTH_MARKERS + (map_markers.COMMONWEALTH_MARKERS[1],)
        with self.assertRaises(ValueError):
            self.markers(markers=dup)


class CheckMapMarkers(unittest.TestCase):
    def setUp(self):
        self.ov = {"world": "W", "location": "WLocation", "spawn": SPAWN, "spawn_cell": [-10, 11],
                   "map_markers": map_markers.overlay_markers(SPAWN, BOUNDS, lambda x, y: 1.0)}
        tags = [m["tag"] for m in self.ov["map_markers"]]
        self.ids = {"bases": {}, "refs": {}, "map_markers": {"W": "000900"},
                    "map_marker_refs": {"W": {t: f"{0x900 + k:06X}" for k, t in enumerate(tags)}}}

    def recs(self, lcsr_tail=map_markers.LCSR_TAIL, drop_lcid=False, flags=0xC00, late_other=False):
        recs = [{"sig": "WRLD", "fid": OWN | 0x803, "flags": 0, "fields": [(b"EDID", z("W"))]},
                {"sig": "REFR", "fid": OWN | 0x810, "flags": 0, "fields": []}]
        rows, lcid = [], []
        for k, m in enumerate(self.ov["map_markers"]):
            fid = OWN | 0x900 + k
            recs.append({"sig": "REFR", "fid": fid, "flags": flags, "fields": [
                (b"EDID", z("WMapMarker" + m["tag"])), (b"NAME", struct.pack("<I", map_markers.MAPMARKER_STAT)),
                (b"DATA", struct.pack("<6f", *m["pos"], 0, 0, 0)), (b"XMRK", b"")]})
            rows.append(struct.pack("<5I", map_markers.MAPMARKER_REF_TYPE, fid, OWN | 0x803,
                                    struct.unpack("<I", struct.pack("<hh", m["cell"][1], m["cell"][0]))[0], lcsr_tail))
            lcid.append(fid)
        fields = [(b"EDID", z("WLocation")), (b"LCSR", b"".join(rows))]
        if not drop_lcid:
            fields.append((b"LCID", struct.pack(f"<{len(lcid)}I", *lcid)))
        recs.append({"sig": "LCTN", "fid": OWN | 0x802, "flags": 0, "fields": fields})
        if late_other:
            recs.append({"sig": "STAT", "fid": OWN | 0x950, "flags": 0, "fields": []})
        return recs

    def test_written_chain_passes(self):
        self.assertEqual(mk.map_marker_problems(self.recs(), 1, self.ov, self.ids), [])
        self.assertEqual(mk.map_marker_ids(self.ids), {0x900, 0x901, 0x902, 0x903})

    def test_zero_tail_fails(self):
        self.assertTrue(mk.map_marker_problems(self.recs(lcsr_tail=0), 1, self.ov, self.ids))

    def test_missing_lcid_fails(self):
        self.assertTrue(any("LCID" in p for p in mk.map_marker_problems(self.recs(drop_lcid=True), 1, self.ov, self.ids)))

    def test_not_persistent_fails(self):
        self.assertTrue(any("persistent" in p for p in mk.map_marker_problems(self.recs(flags=0), 1, self.ov, self.ids)))

    def test_marker_before_another_record_fails(self):
        self.assertTrue(any("before" in p for p in mk.map_marker_problems(self.recs(late_other=True), 1, self.ov, self.ids)))

    def test_moved_marker_fails(self):
        recs = self.recs()
        r = next(r for r in recs if r["fid"] == OWN | 0x902)
        r["fields"][2] = (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))
        self.assertTrue(any("Vault111" in p for p in mk.map_marker_problems(recs, 1, self.ov, self.ids)))

    def test_malformed_expected_positions_return_diagnostics(self):
        recs = self.recs()
        position = self.ov["map_markers"][0]["pos"]
        malformed = (None, 0, [], position[:2], [*position, 42],
                     [float("nan"), *position[1:]], [position[0], float("inf"), position[2]],
                     [position[0], position[1], float("-inf")],
                     [str(position[0]), *position[1:]], [True, *position[1:]],
                     [10 ** 400, *position[1:]])
        for expected in malformed:
            with self.subTest(expected=expected):
                ov = dict(self.ov, map_markers=[dict(m) for m in self.ov["map_markers"]])
                ov["map_markers"][0]["pos"] = expected
                problems = mk.map_marker_problems(recs, 1, ov, self.ids)
                self.assertTrue(any("RedRocket" in p and "expected position" in p for p in problems), problems)
        self.assertEqual(mk.map_marker_problems(recs, 1, self.ov, self.ids), [])

    def test_invalid_expectations_cannot_hide_written_coordinate_drift(self):
        position = self.ov["map_markers"][0]["pos"]
        cases = ((position[:2], [position[0], position[1], position[2] + 250]),
                 ([float("nan"), *position[1:]], [position[0] + 100, position[1], position[2] + 250]))
        for expected, actual in cases:
            with self.subTest(expected=expected):
                recs = self.recs()
                marker = next(r for r in recs if r["fid"] == OWN | 0x900)
                marker["fields"][2] = (b"DATA", struct.pack("<6f", *actual, 0, 0, 0))
                ov = dict(self.ov, map_markers=[dict(m) for m in self.ov["map_markers"]])
                ov["map_markers"][0]["pos"] = expected
                self.assertTrue(mk.map_marker_problems(recs, 1, ov, self.ids))

    def test_finite_tuple_expectations_and_nonfinite_written_positions(self):
        ov = dict(self.ov, map_markers=[dict(m, pos=tuple(m["pos"])) for m in self.ov["map_markers"]])
        self.assertEqual(mk.map_marker_problems(self.recs(), 1, ov, self.ids), [])
        position = self.ov["map_markers"][0]["pos"]
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(actual=value):
                recs = self.recs()
                marker = next(r for r in recs if r["fid"] == OWN | 0x900)
                marker["fields"][2] = (b"DATA", struct.pack("<6f", value, *position[1:], 0, 0, 0))
                self.assertTrue(any("position" in p for p in mk.map_marker_problems(recs, 1, ov, self.ids)))

    def test_single_coc_marker_without_params(self):
        ov = {k: v for k, v in self.ov.items() if k != "map_markers"}
        ids = {"bases": {}, "refs": {}, "map_markers": {"W": "000900"}}
        self.ov["map_markers"] = self.ov["map_markers"][:1]
        recs = self.recs()
        self.assertEqual(mk.map_marker_problems(recs, 1, ov, ids), [])

    def test_doors_after_ignores_the_later_map_markers(self):
        ids = dict(self.ids, doors={"1:F": {"ref": "000810", "base": "000805", "arrival": "000804"}})
        recs = self.recs() + [{"sig": "ACTI", "fid": OWN | 0x805, "flags": 0, "fields": []},
                              {"sig": "REFR", "fid": OWN | 0x804, "flags": 0, "fields": []}]
        first, last = mk.doors_after(recs, 1, ids)
        self.assertEqual(first, 0x804)
        self.assertLess(last, 0x900)

    def test_core64_location_compares_without_its_marker_chain(self):
        a = {"sig": "LCTN", "fid": 1, "flags": 0, "fields": [(b"EDID", z("L")), (b"LCSR", b"x" * 20), (b"LCID", b"abcd")]}
        b = {"sig": "LCTN", "fid": 1, "flags": 0, "fields": [(b"EDID", z("L")), (b"LCSR", b"y" * 80)]}
        self.assertEqual(mk.without_marker_chain(a), mk.without_marker_chain(b))
        c = dict(b, fields=[(b"EDID", z("M"))])
        self.assertNotEqual(mk.without_marker_chain(a), mk.without_marker_chain(c))
        self.assertTrue(mk.is_map_marker_ref(self.recs()[2]))
        self.assertFalse(mk.is_map_marker_ref(self.recs()[1]))


if __name__ == "__main__":
    unittest.main()
