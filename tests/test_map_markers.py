"""Synthetic LCSR fixtures from the Starfield.esm 1.16.244 walk in docs/terrain/map-markers.md. No game files."""
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import map_markers as mm  # noqa: E402

# LC172WorldLocation LCSR, 40 bytes: snow globe then MapMarkerRefType -> 003E5E12.
LC172_LCSR = bytes.fromhex(
    "429A0000" "329A0000" "8CDF0200" "00000000" "FFFFFFFF"
    "1F270200" "125E3E00" "8CDF0200" "00000000" "FFFFFFFF"
)
# LandingOverlay01Location LCSR, 60 bytes: MapMarker then two ship-landing types on the same pad.
LANDING_LCSR = bytes.fromhex(
    "1F270200" "6E863A00" "EA871100" "00000000" "FFFFFFFF"
    "05910000" "C93D0900" "EA871100" "00000000" "FFFFFFFF"
    "02910000" "C93D0900" "EA871100" "00000000" "FFFFFFFF"
)


class LcsrLayout(unittest.TestCase):
    def test_lc172_stride_names_the_map_marker(self):
        rows = mm.parse_lcsr(LC172_LCSR)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["lcrt"], mm.LANDMARK_SNOW_GLOBE_REF_TYPE)
        self.assertEqual(rows[1], {
            "lcrt": mm.MAPMARKER_REF_TYPE,
            "refr": mm.LC172_MAP_MARKER,
            "wrld": mm.LC172_WORLD,
            "pad": 0,
            "tail": 0xFFFFFFFF,
        })

    def test_landing_overlay_adds_ship_pad_lcsr_on_the_same_refr(self):
        rows = mm.parse_lcsr(LANDING_LCSR)
        self.assertEqual([r["lcrt"] for r in rows], [
            mm.MAPMARKER_REF_TYPE,
            mm.SHIP_LANDING_MARKER_REF_TYPE,
            mm.SHIP_LANDING_MARKER_REF_TYPE_LARGE,
        ])
        self.assertEqual(rows[1]["refr"], rows[2]["refr"])
        self.assertEqual(rows[0]["wrld"], 0x001187EA)

    def test_empty_lcsr_is_our_pinned_overlay(self):
        self.assertEqual(mm.parse_lcsr(b""), [])

    def test_truncated_lcsr_is_refused(self):
        with self.assertRaises(ValueError):
            mm.parse_lcsr(LC172_LCSR[:19])

    def test_roundtrip_and_map_marker_helper(self):
        packed = mm.pack_lcsr(mm.parse_lcsr(LC172_LCSR))
        self.assertEqual(packed, LC172_LCSR)
        one = mm.map_marker_lcsr(0x01000DB0, 0x01000803)
        row = mm.parse_lcsr(one)[0]
        self.assertEqual(row["lcrt"], mm.MAPMARKER_REF_TYPE)
        self.assertEqual((row["refr"], row["wrld"]), (0x01000DB0, 0x01000803))

    def test_lc172_marker_fnam_tnam_are_little_endian(self):
        self.assertEqual(struct.pack("<I", mm.LC172_FNAM), bytes.fromhex("1b000000"))
        self.assertEqual(struct.pack("<H", mm.LC172_TNAM), bytes.fromhex("1700"))

    def test_writer_restores_lc172_marker_not_a_landing_overlay(self):
        path = os.path.join(ROOT, "dotnet", "TerrainOverlays", "Program.cs")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("0x3E5E12", src)
        self.assertIn("0x2271F", src)
        self.assertIn("MapMarkerRefType", src)
        self.assertIn('ids["map_markers"]', src)
        self.assertNotIn("0x9105", src)
        self.assertNotIn("ShipLandingMarkerRefType", src)


if __name__ == "__main__":
    unittest.main()
