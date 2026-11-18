"""Synthetic unit tests for `WG1` BTD `LTEX` mapping (`src/fo4sf/terrain/ltex_map.py`).

Zero game files are read; all `LAND` subrecords, `.mat` templates, and `.btd` files are generated in memory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts" / "terrain") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "terrain"))

from fo4sf import btd  # noqa: E402
from fo4sf.terrain import ltex_map as lm  # noqa: E402
from fo4sf.terrain.path_guard import OutputPathRefusedError  # noqa: E402
import make_wg1_redrocket as mwg1  # noqa: E402

SYNTH_TERRAIN_TEMPLATE = {
    "Import": ["Data\\MATERIALS\\Layered\\ShaderModels\\Terrain1Layer.mat"],
    "Objects": [
        {
            "Components": [
                {"Data": {"Name": "DirtFootprints01"}, "Index": 0, "Type": "BSComponentDB::CTName"},
                {"Data": {"ID": "res:44DFC423:0005E661:A06346EA"}, "Index": 0, "Type": "BSMaterial::LayerID"},
            ],
            "Parent": "Data\\MATERIALS\\Layered\\ShaderModels\\Terrain1Layer.mat",
        },
        {
            "Components": [
                {"Data": {"Name": "DirtFootprints01_Layer1"}, "Index": 0, "Type": "BSComponentDB::CTName"},
                {"Data": {"ID": "res:44DFC445:0005E661:A06346EA"}, "Index": 0, "Type": "BSMaterial::MaterialID"},
            ],
            "ID": "res:44DFC423:0005E661:A06346EA",
            "Parent": "res:D785C4ED:0005DEA9:A06346EA",
        },
        {
            "Components": [
                {"Data": {"Name": "DirtFootprints01_TextureSet1"}, "Index": 0, "Type": "BSComponentDB::CTName"},
                {"Data": {"FileName": "textures\\orig_color.dds"}, "Index": 0, "Type": "BSMaterial::MRTextureFile", "Version": 1},
                {"Data": {"FileName": "textures\\orig_normal.dds"}, "Index": 1, "Type": "BSMaterial::MRTextureFile", "Version": 1},
                {"Data": {"FileName": "textures\\orig_rough.dds"}, "Index": 3, "Type": "BSMaterial::MRTextureFile", "Version": 1},
                {"Data": {"FileName": "textures\\orig_ao.dds"}, "Index": 5, "Type": "BSMaterial::MRTextureFile", "Version": 1},
                {"Data": {"FileName": "textures\\orig_height.dds"}, "Index": 6, "Type": "BSMaterial::MRTextureFile", "Version": 1},
            ],
            "ID": "res:44DFC48E:0005E661:A06346EA",
            "Parent": "res:D785C5BE:0005DEA9:A06346EA",
        },
    ],
    "Summary": {
        "Layer1": {
            "Parent": "Data\\MATERIALS\\Layered\\ShaderModels\\Terrain1Layer.mat",
            "Textures": {
                "Albedo": {"File": "textures\\orig_color.dds", "UseReplacement": False},
                "Normal": {"File": "textures\\orig_normal.dds", "UseReplacement": False},
                "Roughness": {"File": "textures\\orig_rough.dds", "UseReplacement": False},
                "AmbientOcclusion": {"File": "textures\\orig_ao.dds", "UseReplacement": False},
                "Height": {"File": "textures\\orig_height.dds", "UseReplacement": False},
            },
        }
    },
    "Version": 1,
}


class BtdLtexMappingTests(unittest.TestCase):
    def test_parse_fo4_land_layers_btxt_atxt_vtxt_sum_to_one(self) -> None:
        # Quadrant 0: BTXT = 0x01D1D3, ATXT layer 0 = 0x021336 (opacity 0.6 everywhere), layer 1 = 0x01F78C (opacity 0.25 at (0,0))
        btxt0 = (b"BTXT", struct.pack("<IBBh", 0x01D1D3, 0, 0, -1))
        atxt0 = (b"ATXT", struct.pack("<IBBh", 0x021336, 0, 0, 0))
        vtxt0 = (b"VTXT", b"".join(struct.pack("<HBBf", pos, 0, 0, 0.6) for pos in range(17 * 17)))
        atxt1 = (b"ATXT", struct.pack("<IBBh", 0x01F78C, 0, 0, 1))
        vtxt1 = (b"VTXT", struct.pack("<HBBf", 0, 0, 0, 0.25))

        parsed = lm.parse_fo4_land_layers([btxt0, atxt0, vtxt0, atxt1, vtxt1], [], "Fallout4.esm")
        q0 = parsed[0]
        total = sum(arr for arr in q0.values())
        self.assertTrue(np.allclose(total, 1.0, atol=1e-5))
        # At (0, 0): base 01D1D3 = (1 - 0.6) * (1 - 0.25) = 0.30; 021336 = 0.6 * 0.75 = 0.45; 01F78C = 0.25
        self.assertAlmostEqual(float(q0["Fallout4.esm:01D1D3"][0, 0]), 0.30, places=5)
        self.assertAlmostEqual(float(q0["Fallout4.esm:021336"][0, 0]), 0.45, places=5)
        self.assertAlmostEqual(float(q0["Fallout4.esm:01F78C"][0, 0]), 0.25, places=5)
        # Quadrant 2 (no BTXT/ATXT) defaults cleanly to Fallout4.esm:000000 = 1.0
        self.assertIn("Fallout4.esm:000000", parsed[2])
        self.assertTrue(np.allclose(parsed[2]["Fallout4.esm:000000"], 1.0))

    def test_encode_and_decode_btd_ltex_window_matches_dominant_over_90_percent(self) -> None:
        # 5 x 5 SF cells = 10 x 10 = 100 BTD quadrants; 96 quadrants use 4 mapped FO4 LTEXs with multi-layer blends,
        # and 4 quadrants use an unmapped rare FO4 LTEX -> expected dominant match = 96% (>= 90%)!
        n_cells = 5
        ltex_mapping = {
            "Fallout4.esm:000000": 0x01000F00,
            "Fallout4.esm:01D1D3": 0x01000F01,
            "Fallout4.esm:021336": 0x01000F02,
            "Fallout4.esm:01F78C": 0x01000F03,
            "Fallout4.esm:021C68": 0x01000F04,
        }
        mapped_keys = list(ltex_mapping.keys())
        fo4_quads: dict[tuple[int, int], dict[str, np.ndarray]] = {}
        for fqx in range(-12, 14):
            for fqy in range(-12, 14):
                if fqx in (-10, -9) and fqy in (-10, -9):
                    # Rare unmapped FO4 LTEX in SW corner
                    fo4_quads[(fqx, fqy)] = {"Fallout4.esm:0FFFFF": np.ones((17, 17), dtype=np.float32)}
                else:
                    dom_k = mapped_keys[(fqx * 3 + fqy * 5) % len(mapped_keys)]
                    sec_k = mapped_keys[(fqx * 3 + fqy * 5 + 1) % len(mapped_keys)]
                    g_dom = np.full((17, 17), 0.72, dtype=np.float32)
                    g_sec = np.full((17, 17), 0.28, dtype=np.float32)
                    fo4_quads[(fqx, fqy)] = {dom_k: g_dom, sec_k: g_sec}

        table, quad_map, weights, stats = lm.encode_btd_ltex_window(
            fo4_quads,
            n_sf_cells=n_cells,
            origin_cw_m=(0.0, 0.0),
            ltex_mapping=ltex_mapping,
        )
        self.assertGreater(len(table), 1)
        self.assertEqual(len(table), 6)  # 5 mapped + 1 fallback

        raw_h = np.zeros((n_cells * 128, n_cells * 128), dtype=np.uint16)
        btd_bytes = btd.write(btd.Btd(6, -10.0, 50.0, table, raw_h, weights, quad_map))
        decoded = btd.read(btd_bytes)

        vrep = lm.verify_btd_against_fo4_dominants(decoded, stats["quad_gt_dominant"], ltex_mapping)
        self.assertGreater(vrep["ltex_table_size"], 1)
        self.assertGreaterEqual(vrep["dominant_blended_match_ratio"], 0.90)
        self.assertGreaterEqual(vrep["base_slot_match_ratio"], 0.90)

    def test_build_terrain_mat_remaps_ids_and_binds_three_pbr_maps(self) -> None:
        m1 = lm.build_terrain_mat(
            SYNTH_TERRAIN_TEMPLATE,
            "FO4WG1_LDriedGrass01",
            "textures/fo4wg1/landscape/ground/driedgrass01_color.dds",
            "textures/fo4wg1/landscape/ground/driedgrass01_normal.dds",
            "textures/fo4wg1/landscape/ground/driedgrass01_rough.dds",
        )
        m2 = lm.build_terrain_mat(
            SYNTH_TERRAIN_TEMPLATE,
            "FO4WG1_LAsphalt01",
            "textures/fo4wg1/landscape/roads/asphalt01_color.dds",
            "textures/fo4wg1/landscape/roads/asphalt01_normal.dds",
            "textures/fo4wg1/landscape/roads/asphalt01_rough.dds",
        )
        ids1 = {o["ID"] for o in m1["Objects"] if "ID" in o}
        ids2 = {o["ID"] for o in m2["Objects"] if "ID" in o}
        orig_ids = {o["ID"] for o in SYNTH_TERRAIN_TEMPLATE["Objects"] if "ID" in o}
        self.assertTrue(ids1.isdisjoint(orig_ids))
        self.assertTrue(ids1.isdisjoint(ids2))

        s = json.dumps(m1)
        self.assertNotIn("orig_ao.dds", s)
        self.assertNotIn("orig_height.dds", s)
        self.assertIn("driedgrass01_color.dds", s)
        self.assertTrue(m1["Summary"]["Layer1"]["Textures"]["AmbientOcclusion"]["UseReplacement"])

    def test_wg1_cli_refuses_unsafe_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wt = os.path.join(tmp, "wt")
            os.makedirs(os.path.join(wt, ".git"), exist_ok=True)
            with self.assertRaises(OutputPathRefusedError):
                mwg1.check_wg1_stage(os.path.join(wt, "out"))


if __name__ == "__main__":
    unittest.main()
