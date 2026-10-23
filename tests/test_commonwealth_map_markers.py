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


class ExportedMarkers(unittest.TestCase):
    """Fo4Land export-mapmarkers rows (dotnet/Fo4Land/MapMarkersExport.cs) into stage entries after the fixed four."""
    DOC = {"plugin": "Fallout4.esm", "world": "Commonwealth", "markers": [
        {"fid": "00072A48", "name": "Sanctuary Hills", "pos": [-80768.19, 88174.80, 0]},     # one of the fixed four
        {"fid": "0001F2A9", "name": "Abernathy Farm", "pos": [-81000.0, 86000.0, 0]},
        {"fid": "0001F2AA", "name": None, "pos": [0, 0, 0]},
        {"fid": "0001F2AB", "name": "Far Away", "pos": [-300000.0, 0.0, 0]},              # beyond the overlay
        {"fid": "0001F2AC", "name": "Lost", "pos": [float("nan"), 0.0, 0]},
    ]}

    def test_named_markers_load_without_the_fixed_four(self):
        rows, left = map_markers.load_fo4_markers(self.DOC)
        self.assertEqual([r[0] for r in rows], ["M01F2A9", "M01F2AB"])
        self.assertEqual(sorted(e["reason"] for e in left),
                         ["no finite position", "no name", "one of the core's fixed markers"])

    def test_outside_the_overlay_is_left_out_not_fatal(self):
        rows, _ = map_markers.load_fo4_markers(self.DOC)
        entries, left = map_markers.extra_markers(rows, BOUNDS, lambda x, y: 2.0)
        self.assertEqual([(e["tag"], e["name"]) for e in entries], [("M01F2A9", "Abernathy Farm")])
        self.assertEqual(entries[0]["src"], "01F2A9:Fallout4.esm")
        self.assertAlmostEqual(entries[0]["pos"][0], -81000.0 / 70, places=3)
        self.assertEqual(entries[0]["pos"][2], 2.0)
        self.assertEqual([e["src"] for e in left], ["01F2AB:Fallout4.esm"])
        self.assertIn("outside the overlay", left[0]["reason"])

    def test_a_marker_on_a_fixed_one_is_left_out(self):
        # FO4's own Red Rocket marker would draw a second icon next to the core's, which sits on the COC arrival
        fixed = map_markers.overlay_markers(SPAWN, BOUNDS, lambda x, y: 0.0)
        rr = ("M01F2B0", "Red Rocket Truck Stop", 0x1F2B0, (SPAWN[0] + 40) * 70, (SPAWN[1] - 30) * 70)
        far = ("M01F2B1", "Abernathy Farm", 0x1F2B1, -40000.0, 20000.0)
        # a differently named place on the same spot is its own location (the Museum of Freedom in Concord)
        other = ("M01F2B2", "Red Rocket Garage", 0x1F2B2, (SPAWN[0] + 30) * 70, (SPAWN[1] - 20) * 70)
        entries, left = map_markers.extra_markers([rr, far, other], BOUNDS, lambda x, y: 0.0, fixed=fixed)
        self.assertEqual([e["tag"] for e in entries], ["M01F2B1", "M01F2B2"])
        self.assertEqual(left, [{"src": "01F2B0:Fallout4.esm",
                                 "reason": "Red Rocket Truck Stop: within 100 m of the fixed marker RedRocket"}])

    def test_a_same_named_marker_close_to_a_kept_one_is_left_out(self):
        # FO4's USS Constitution: two markers 4 m apart where the ship comes to rest; the first in FormID order stays.
        # A same-named place farther off (FO4's two "Cave" markers) is another place and stays too
        rows = [("M01F2C0", "USS Constitution", 0x1F2C0, 27160.0, -3990.0),
                ("M01F2C1", "Cave", 0x1F2C1, -75390.0, -89810.0),
                ("M01F2C2", "USS Constitution", 0x1F2C2, 27370.0, -3850.0),
                ("M01F2C3", "Cave", 0x1F2C3, -72030.0, -116760.0)]
        entries, left = map_markers.extra_markers(rows, BOUNDS, lambda x, y: 0.0)
        self.assertEqual([e["tag"] for e in entries], ["M01F2C0", "M01F2C1", "M01F2C3"])
        self.assertEqual(left, [{"src": "01F2C2:Fallout4.esm",
                                 "reason": "USS Constitution: within 100 m of the kept marker M01F2C0"}])

    def test_a_landing_spot_is_landingoverlay01_moved_to_the_pad(self):
        # the pad on the ground at (x, y); the trigger and marker keep LandingOverlay01's offsets from it, heights
        # included; the heading keeps its x, y offset and stands on its own ground, lifted as the markers' arrivals
        ground = lambda x, y: 50.0 + 0.01 * (x - y)                              # noqa: E731  (a slope)
        spot = map_markers.landing_spot(-759.0, 2207.0, BOUNDS, ground, 2.5)
        vanilla = map_markers.LANDING_OVERLAY01
        (vx, vy, vz), _ = vanilla["pad"]
        self.assertEqual(spot["pad"]["pos"], [-759.0, 2207.0, round(ground(-759.0, 2207.0), 4)])
        for part in ("trigger", "marker", "heading"):
            (px, py, pz), rot = vanilla[part]
            got = spot[part]["pos"]
            self.assertAlmostEqual(got[0] - spot["pad"]["pos"][0], px - vx, places=3, msg=part)
            self.assertAlmostEqual(got[1] - spot["pad"]["pos"][1], py - vy, places=3, msg=part)
            want_z = ground(got[0], got[1]) + 2.5 if part == "heading" else spot["pad"]["pos"][2] + pz - vz
            self.assertAlmostEqual(got[2], want_z, places=3, msg=part)
            self.assertEqual(spot[part]["rot"], list(rot), part)
            self.assertEqual(spot[part]["cell"], map_markers.sf_cell(got[0], got[1]), part)
        self.assertEqual(spot["pad"]["rot"], list(vanilla["pad"][1]))
        self.assertEqual(spot["marker"]["cell"], [-8, 21])                     # 11 m south of the pad: the next cell
        self.assertEqual(spot["pad"]["cell"], [-8, 22])
        self.assertEqual((spot["tag"], spot["name"]), ("RedRocketNorth", "Landing Area"))

    def test_a_landing_spot_stays_a_cell_inside_the_overlay(self):
        map_markers.landing_spot(3100.0, -3100.0, BOUNDS, lambda x, y: 0.0, 2.5)
        for x, y in ((3100.1, 0.0), (0.0, -3100.1)):
            with self.assertRaises(ValueError) as e:
                map_markers.landing_spot(x, y, BOUNDS, lambda x, y: 0.0, 2.5)
            self.assertIn("less than 100 m inside the overlay", str(e.exception))

    def test_another_world_is_refused(self):
        with self.assertRaises(ValueError):
            map_markers.load_fo4_markers(dict(self.DOC, world="FarHarbor"))

    def test_the_check_takes_the_extra_markers(self):
        rows, _ = map_markers.load_fo4_markers(self.DOC)
        extra, _ = map_markers.extra_markers(rows, BOUNDS, lambda x, y: 1.0)
        check = CheckMapMarkers("test_written_chain_passes")
        check.setUp()
        check.ov["map_markers"] += extra
        tags = [m["tag"] for m in check.ov["map_markers"]]
        check.ids["map_marker_refs"]["W"] = {t: f"{0x900 + k:06X}" for k, t in enumerate(tags)}
        self.assertEqual(mk.map_marker_problems(check.recs(), 1, check.ov, check.ids), [])


class WriterSource(unittest.TestCase):
    def test_writer_enables_the_markers(self):
        # CI has no .NET: the writer's source must clear LC172's Initially Disabled bit and add no LCID (18 Oct: no
        # icon showed with 0xC00 + LCID)
        src = (root / "dotnet" / "TerrainOverlays" / "Program.cs").read_text(encoding="utf-8")
        self.assertIn("marker.MajorRecordFlagsRaw = (marker.MajorRecordFlagsRaw | 0x400) & ~0x800;", src)
        self.assertNotIn("MasterInitiallyDisabledReferences.Add", src)
        self.assertNotIn("MajorRecordFlagsRaw |= 0xC00", src)


class CheckMapMarkers(unittest.TestCase):
    def setUp(self):
        self.ov = {"world": "W", "location": "WLocation", "spawn": SPAWN, "spawn_cell": [-10, 11],
                   "map_markers": map_markers.overlay_markers(SPAWN, BOUNDS, lambda x, y: 1.0)}
        tags = [m["tag"] for m in self.ov["map_markers"]]
        self.ids = {"bases": {}, "refs": {}, "map_markers": {"W": "000900"},
                    "map_marker_refs": {"W": {t: f"{0x900 + k:06X}" for k, t in enumerate(tags)}}}

    def recs(self, lcsr_tail=map_markers.LCSR_TAIL, lcid=False, flags=0x400, late_other=False):
        recs = [{"sig": "WRLD", "fid": OWN | 0x803, "flags": 0, "fields": [(b"EDID", z("W"))]},
                {"sig": "REFR", "fid": OWN | 0x810, "flags": 0, "fields": []}]
        rows, lcids = [], []
        for k, m in enumerate(self.ov["map_markers"]):
            fid = OWN | 0x900 + k
            recs.append({"sig": "REFR", "fid": fid, "flags": flags, "fields": [
                (b"EDID", z("WMapMarker" + m["tag"])), (b"NAME", struct.pack("<I", map_markers.MAPMARKER_STAT)),
                (b"DATA", struct.pack("<6f", *m["pos"], 0, 0, 0)), (b"XMRK", b"")]})
            rows.append(struct.pack("<5I", map_markers.MAPMARKER_REF_TYPE, fid, OWN | 0x803,
                                    struct.unpack("<I", struct.pack("<hh", m["cell"][1], m["cell"][0]))[0], lcsr_tail))
            lcids.append(fid)
        fields = [(b"EDID", z("WLocation")), (b"LCSR", b"".join(rows))]
        if lcid:
            fields.append((b"LCID", struct.pack(f"<{len(lcids)}I", *lcids)))
        recs.append({"sig": "LCTN", "fid": OWN | 0x802, "flags": 0, "fields": fields})
        if late_other:
            recs.append({"sig": "STAT", "fid": OWN | 0x950, "flags": 0, "fields": []})
        return recs

    def test_written_chain_passes(self):
        self.assertEqual(mk.map_marker_problems(self.recs(), 1, self.ov, self.ids), [])
        self.assertEqual(mk.map_marker_ids(self.ids), {0x900, 0x901, 0x902, 0x903})

    def test_zero_tail_fails(self):
        self.assertTrue(mk.map_marker_problems(self.recs(lcsr_tail=0), 1, self.ov, self.ids))

    def test_markers_in_lcid_fail(self):
        self.assertTrue(any("LCID" in p for p in mk.map_marker_problems(self.recs(lcid=True), 1, self.ov, self.ids)))

    def test_initially_disabled_marker_fails(self):
        # LC172's 0xC00 hid every icon in game (18 Oct)
        self.assertTrue(any("enabled" in p for p in mk.map_marker_problems(self.recs(flags=0xC00), 1, self.ov, self.ids)))

    def test_not_persistent_fails(self):
        self.assertTrue(any("persistent" in p for p in mk.map_marker_problems(self.recs(flags=0), 1, self.ov, self.ids)))

    def test_marker_before_another_record_fails(self):
        self.assertTrue(any("before" in p for p in mk.map_marker_problems(self.recs(late_other=True), 1, self.ov, self.ids)))

    def test_moved_marker_fails(self):
        recs = self.recs()
        r = next(r for r in recs if r["fid"] == OWN | 0x902)
        r["fields"][2] = (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))
        self.assertTrue(any("Vault111" in p for p in mk.map_marker_problems(recs, 1, self.ov, self.ids)))

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
