"""Synthetic path/constant fixtures for docs/terrain/surface-map.md. No game files."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import surface_map as sm  # noqa: E402


class LodsettingsPath(unittest.TestCase):
    def test_world_edid_lowercases_like_lc172world(self):
        self.assertEqual(sm.lodsettings_rel("LC172World"), "lodsettings/lc172world.lod")
        self.assertEqual(
            sm.lodsettings_rel(sm.WORLD_EDID), "lodsettings/fo4core_commonwealth.lod"
        )

    def test_blank_or_pathed_edid_is_refused(self):
        for bad in ("", "  x", "x/y", "a\\b"):
            with self.assertRaises(ValueError):
                sm.lodsettings_rel(bad)


class WorldObjectLodVsConvertedFo4(unittest.TestCase):
    def test_generated_lod_indices_0_to_3_count(self):
        for i in range(4):
            path = f"meshes/lod/generated/newatlantis_something_lod_{i}.nif"
            self.assertTrue(sm.is_starfield_world_lod_mesh(path))
            self.assertFalse(sm.is_converted_fo4_lod_mesh(path))

    def test_fo4core_lod_nif_is_not_world_object_lod(self):
        path = "meshes/fo4core/lod/neighborhoods/backbay/backbay02_bld01lod.nif"
        self.assertTrue(sm.is_converted_fo4_lod_mesh(path))
        self.assertFalse(sm.is_starfield_world_lod_mesh(path))
        self.assertFalse(sm.is_starfield_world_lod_mesh("meshes/lod/generated/x_lod_4.nif"))

    def test_backslash_and_case_do_not_reclassify(self):
        self.assertTrue(
            sm.is_starfield_world_lod_mesh(r"Meshes\LOD\generated\City_lod_0.NIF")
        )
        self.assertTrue(
            sm.is_converted_fo4_lod_mesh(r"Meshes\FO4Core\LOD\unique\cit\x_lod_0.nif")
        )


class LodsettingsStub(unittest.TestCase):
    def test_stub_is_20_bytes_matching_vanilla_prefix(self):
        data = sm.make_lodsettings_stub()
        self.assertEqual(len(data), 20)
        # Matches object-lod.md example prefix for -2,-2,size=8
        self.assertEqual(data[:10].hex(), "fefffffffeffffff0800")

    def test_custom_mins_and_size(self):
        data = sm.make_lodsettings_stub(min_x=0, min_y=1, cell_size=16)
        self.assertEqual(data[:8], b"\x00\x00\x00\x00\x01\x00\x00\x00")
        self.assertEqual(data[8:10], b"\x10\x00")

    def test_range_checks(self):
        with self.assertRaises(ValueError):
            sm.make_lodsettings_stub(min_x=100000)
        with self.assertRaises(ValueError):
            sm.make_lodsettings_stub(cell_size=70000)
