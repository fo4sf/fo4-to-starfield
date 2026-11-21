"""Unit tests for `src/fo4sf/core/world_registry.json` and `src/fo4sf/core/world_registry.py` (`WS3`)."""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from fo4sf.core.start_worlds import START_WORLD_TABLE  # noqa: E402 (read-only import per R2/WS3)
from fo4sf.core.world_registry import (  # noqa: E402
    ALLOWED_PART_STATUSES,
    CURRENT_PIPBOY_DISC_CAPACITY,
    DEFAULT_REGISTRY_PATH,
    REQUIRED_STATUS_PARTS,
    RegistryError,
    load_world_registry,
    parse_world_registry,
)


class WorldRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_world_registry()
        with open(DEFAULT_REGISTRY_PATH, encoding="utf-8") as f:
            cls.raw_doc = json.load(f)

    def test_required_worlds_bounds_and_statuses(self) -> None:
        expected_keys = {
            "Commonwealth",
            "DiamondCity",
            "Goodneighbor",
            "SanctuaryHillsWorld",
            "DiamondCityFX",
            "Commonwealth_DLCRobot",
            "Commonwealth_DLCCoast",
            "Commonwealth_DLCworkshop03",
            "Commonwealth_DLCNukaWorld",
            "FarHarbor",
            "DLC03VRWorldspace",
            "NukaWorld",
            "NukaWorldAmphitheater",
            "NukaWorldMarket",
            "CapitalWasteland",
            "MojaveWasteland",
            "Appalachia",
            "SouthernCalifornia",
            "NorthernCalifornia",
            "MidwestCorridor",
        }
        self.assertEqual(set(self.registry.worlds.keys()), expected_keys)
        self.assertIs(self.registry.get_world("DLC03FarHarbor"), self.registry.get_world("FarHarbor"))

        cw = self.registry.get_world("Commonwealth")
        self.assertEqual(cw.planned_starfield_world.host_planet, "MarsPlanetData")
        self.assertEqual(cw.planned_starfield_world.measured_merge_offset, (-1200.0, -2700.0))
        self.assertEqual(cw.bounds.land_bbox, (-96, 95, -96, 95))

        fh = self.registry.get_world("FarHarbor")
        self.assertEqual(fh.bounds.land_bbox, (-29, 20, -21, 31))
        self.assertIsNone(fh.planned_starfield_world.measured_merge_offset)

        nw = self.registry.get_world("NukaWorld")
        self.assertEqual(nw.bounds.land_bbox, (-32, 32, -32, 32))
        self.assertIsNone(nw.planned_starfield_world.measured_merge_offset)

        for w in self.registry.worlds.values():
            self.assertEqual(set(w.status.keys()), set(REQUIRED_STATUS_PARTS))
            for part, ps in w.status.items():
                self.assertIn(ps.state, ALLOWED_PART_STATUSES, f"{w.key}.{part}")
                rel_file = ps.evidence.split("#", 1)[0]
                self.assertTrue(
                    os.path.isfile(os.path.join(REPO, rel_file)),
                    f"{w.key}.{part} evidence file missing in repo: {rel_file}",
                )

    def test_pipboy_plugin_codes_unique_and_preserve_existing_slots(self) -> None:
        codes = [
            w.planned_starfield_world.pipboy_plugin_code
            for w in self.registry.worlds.values()
            if w.planned_starfield_world.pipboy_plugin_code is not None
        ]
        self.assertEqual(len(codes), len(set(codes)))
        # Existing codes 1..4 in FO4SF_PipboyTravel.psc + planned 5..6 for Far Harbor and Nuka-World
        self.assertEqual(self.registry.world_for_plugin_code(1).planned_starfield_world.plugin, "FO4TerrainCore.esm")  # type: ignore[union-attr]
        self.assertEqual(self.registry.world_for_plugin_code(2).planned_starfield_world.plugin, "FO4CapitalWasteland.esm")  # type: ignore[union-attr]
        self.assertEqual(self.registry.world_for_plugin_code(3).planned_starfield_world.plugin, "FO4Mojave.esm")  # type: ignore[union-attr]
        self.assertEqual(self.registry.world_for_plugin_code(4).planned_starfield_world.plugin, "FO4Appalachia.esm")  # type: ignore[union-attr]
        self.assertEqual(self.registry.world_for_plugin_code(5).key, "FarHarbor")  # type: ignore[union-attr]
        self.assertEqual(self.registry.world_for_plugin_code(6).key, "NukaWorld")  # type: ignore[union-attr]

        mutated = copy.deepcopy(self.raw_doc)
        mutated["worlds"][9]["planned_starfield_world"]["pipboy_plugin_code"] = 1
        with self.assertRaises(RegistryError):
            parse_world_registry(mutated)

    def test_marker_index_ranges_do_not_overlap(self) -> None:
        slices = []
        for w in self.registry.worlds.values():
            rng = w.planned_starfield_world.marker_index_range
            if rng is not None:
                self.assertEqual(rng[1] - rng[0], w.bounds.map_marker_count, w.key)
                slices.append((rng[0], rng[1], w.key))
        slices.sort()
        for i in range(len(slices) - 1):
            self.assertLessEqual(
                slices[i][1],
                slices[i + 1][0],
                f"Overlap between {slices[i]} and {slices[i + 1]}",
            )

        mutated = copy.deepcopy(self.raw_doc)
        mutated["worlds"][1]["planned_starfield_world"]["marker_index_range"] = [300, 314]
        with self.assertRaises(RegistryError):
            parse_world_registry(mutated)

    def test_start_worlds_other_game_rows_match_read_only(self) -> None:
        other_titles = set()
        for start_key, desc in START_WORLD_TABLE.items():
            self.assertTrue(self.registry.has_world(desc.world_id), f"Missing world_id {desc.world_id} for {start_key}")
            w = self.registry.get_world(desc.world_id)
            self.assertEqual(w.game, desc.title, f"Game title mismatch on {start_key}")
            ref_by_key = {sd.key: sd for sd in w.start_descriptors}
            self.assertIn(start_key, ref_by_key)
            self.assertEqual(ref_by_key[start_key].start_cell, desc.start_cell)
            self.assertEqual(ref_by_key[start_key].surface_anchor, desc.surface_anchor)
            if desc.title != "FO4":
                other_titles.add(desc.title)
                self.assertEqual(w.kind, "other_game_world")

        self.assertEqual(other_titles, {"FO1", "FO2", "FOT", "FO3", "FNV", "FO76"})

    def test_reports_pipboy_discovery_capacity_shortfall_by_world_name(self) -> None:
        report = self.registry.discovery_capacity_report(CURRENT_PIPBOY_DISC_CAPACITY)
        summary = report.format_summary()
        print(summary)

        self.assertEqual(report.capacity_bits, 336)
        self.assertEqual(report.total_reserved_markers, 418)
        self.assertFalse(report.fits_capacity)
        self.assertEqual(report.shortfall_markers, 82)
        self.assertEqual(report.required_globals_24bit, 18)
        self.assertEqual(report.additional_globals_needed, 4)

        by_world = {e.world_key: e for e in report.overflow_by_world}
        self.assertEqual(
            list(by_world.keys()),
            ["FarHarbor", "NukaWorld", "NukaWorldAmphitheater", "NukaWorldMarket"],
        )
        self.assertEqual(by_world["FarHarbor"].overflow_markers, 37)
        self.assertEqual(by_world["NukaWorld"].overflow_markers, 43)
        self.assertEqual(by_world["NukaWorldAmphitheater"].overflow_markers, 1)
        self.assertEqual(by_world["NukaWorldMarket"].overflow_markers, 1)
        for wname in ("FarHarbor", "NukaWorld", "NukaWorldAmphitheater", "NukaWorldMarket"):
            self.assertIn(wname, summary)

    def test_locations_count_and_strict_redaction(self) -> None:
        locs = self.registry.all_locations()
        self.assertEqual(len(locs), 487)
        base_locs = [l for l in locs if l.plugin == "Fallout4.esm"]
        self.assertEqual(len(base_locs), 393)

        ident_re = re.compile(r"^[A-Za-z0-9_]+$")
        hex_re = re.compile(r"^0x[0-9A-F]{6}$")
        for loc in locs:
            self.assertRegex(loc.edid, ident_re)
            self.assertRegex(loc.form_id, hex_re)

        # Ensure JSON holds no prose strings (every non-path string <= 64 chars) and rejects PC paths
        path_keys = {"evidence", "map_picture"}

        def walk_strings(node: object, key_name: str = "") -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk_strings(v, k)
            elif isinstance(node, list):
                for item in node:
                    walk_strings(item, key_name)
            elif isinstance(node, str) and key_name not in path_keys:
                self.assertLessEqual(len(node), 64, f"Unexpected long prose string on {key_name}: {node!r}")

        walk_strings(self.raw_doc)

        bad_path_doc = copy.deepcopy(self.raw_doc)
        bad_path_doc["worlds"][0]["status"]["terrain"]["evidence"] = "X:/synthetic_private/private.json"
        with self.assertRaises(RegistryError):
            parse_world_registry(bad_path_doc)


if __name__ == "__main__":
    unittest.main()
