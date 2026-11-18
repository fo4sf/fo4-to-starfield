"""Unit and synthetic end-to-end tests for Phase 2 Track C (`2i`) Route & Vault 111 Loot."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(REPO, "src"), os.path.join(REPO, "scripts", "loot")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_route_loot  # noqa: E402
from fo4sf.loot.tables import (  # noqa: E402
    CREDITS_FORM_ID,
    ROUTE_LOOT_IDS_JSON,
    ROUTE_LOOT_MASTERS,
    ROUTE_LOOT_PLUGIN,
    corridor_distance_m,
    load_route_loot_spec,
    validate_route_loot_doc,
)


class RouteLootTableTests(unittest.TestCase):
    def test_committed_table_is_valid_and_free_of_game_strings(self) -> None:
        with open(ROUTE_LOOT_IDS_JSON, encoding="utf-8") as f:
            raw_doc = json.load(f)
        spec = validate_route_loot_doc(raw_doc)
        self.assertEqual(spec.plugin, ROUTE_LOOT_PLUGIN)
        self.assertEqual(spec.masters, ROUTE_LOOT_MASTERS)
        self.assertEqual(spec.corridor_radius_m, 600.0)
        self.assertGreaterEqual(spec.vault_min_ammo_rounds, 48)
        self.assertGreaterEqual(spec.vault_min_stimpaks, 2)
        self.assertGreater(len(spec.fo4_container_categories), 50)

    def test_rejects_game_display_string_in_json(self) -> None:
        with open(ROUTE_LOOT_IDS_JSON, encoding="utf-8") as f:
            doc = json.load(f)
        bad = copy.deepcopy(doc)
        bad["categories"]["ammo"][0]["name"] = "10mm Rounds"
        with self.assertRaises(ValueError):
            validate_route_loot_doc(bad)

        bad_val = copy.deepcopy(doc)
        bad_val["fo4_container_categories"]["0x038C1E"] = "Raider Ammo Box"
        with self.assertRaises(ValueError):
            validate_route_loot_doc(bad_val)

    def test_rejects_insufficient_vault111_ammo(self) -> None:
        with open(ROUTE_LOOT_IDS_JSON, encoding="utf-8") as f:
            doc = json.load(f)
        bad = copy.deepcopy(doc)
        for item in bad["categories"]["vault_armory"]:
            if item["id"].lower() == bad["vault111"]["ammo_id"].lower():
                item["count"] = 24
        with self.assertRaises(ValueError):
            validate_route_loot_doc(bad)

    def test_corridor_distance_geometry(self) -> None:
        spec = load_route_loot_spec()
        # Sanctuary, Red Rocket, and Concord points lie directly on the polyline.
        for x, y in spec.corridor_polyline_m:
            self.assertAlmostEqual(corridor_distance_m(x, y, spec.corridor_polyline_m), 0.0, places=4)
        # Vault 111 entrance (-1305, 1365) is within 600 m of Sanctuary (-1129, 1280).
        self.assertLessEqual(corridor_distance_m(-1305.0, 1365.0, spec.corridor_polyline_m), 600.0)
        # Diamond City / south Commonwealth (0, -500) is well outside 600 m.
        self.assertGreater(corridor_distance_m(0.0, -500.0, spec.corridor_polyline_m), 600.0)


class RouteLootWriterAndStageTests(unittest.TestCase):
    def test_dotnet_selftest_and_make_route_loot_stage_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scratch = os.path.join(tmp, "selftest")
            dll = make_route_loot.build_routeloot_dll()
            r = subprocess.run(["dotnet", dll, "selftest", scratch], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            self.assertIn("selftest: PASS", r.stdout)

            # Reuse synthetic Starfield.esm, FO4TerrainCore.esm, and FO4Port.esm created by selftest
            sf_esm = os.path.join(scratch, "Starfield.esm")
            core_esm = os.path.join(scratch, "FO4TerrainCore.esm")
            port_esm = os.path.join(scratch, "FO4Port.esm")
            stage_out = os.path.join(tmp, "staged-17")

            rc = make_route_loot.main(
                [
                    "stage",
                    "--out",
                    stage_out,
                    "--starfield",
                    sf_esm,
                    "--core",
                    core_esm,
                    "--port",
                    port_esm,
                ]
            )
            self.assertEqual(rc, 0)

            plan_path = os.path.join(stage_out, "plan.json")
            census_path = os.path.join(stage_out, "census.json")
            plugin_path = os.path.join(stage_out, ROUTE_LOOT_PLUGIN)
            self.assertTrue(os.path.isfile(plugin_path))
            self.assertTrue(os.path.isfile(plan_path))
            self.assertTrue(os.path.isfile(census_path))

            with open(census_path, encoding="utf-8") as f:
                census = json.load(f)
            self.assertGreater(census["route_containers_with_non_credit_items"], 0)
            self.assertGreaterEqual(census["vault111"]["armory_case_pistols"], 1)
            self.assertGreaterEqual(census["vault111"]["armory_case_ammo_rounds"], 48)
            self.assertGreaterEqual(census["vault111"]["armory_case_stimpaks"], 2)

            v_rc = make_route_loot.main(
                [
                    "verify",
                    "--exp-dir",
                    stage_out,
                    "--plan",
                    plan_path,
                    "--starfield",
                    sf_esm,
                    "--core",
                    core_esm,
                    "--port",
                    port_esm,
                ]
            )
            self.assertEqual(v_rc, 0)

            # Tampering plugin bytes must fail verify.
            with open(plugin_path, "ab") as f:
                f.write(b"\x00")
            bad_problems = make_route_loot.verify_stage_dir(stage_out, plan_path, sf_esm, core_esm, port_esm)
            self.assertTrue(any("plugin sha256" in p for p in bad_problems))


if __name__ == "__main__":
    unittest.main()
