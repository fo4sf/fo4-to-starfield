"""Synthetic unit tests for `WD2` & `WD3` DLC terrain-only worlds and `overlay_postpatch.py`."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fo4sf import btd, fo4land, overlay_grid as og  # noqa: E402
from fo4sf.core.world_registry import (  # noqa: E402
    HOME_EARTH_RADIUS_KM,
    LANDING_HALF_WIDTH_CELLS,
    MARS_RADIUS_KM,
    load_world_registry,
    parse_world_registry,
    planet_separation_cells,
)
from fo4sf.terrain import overlay_postpatch as opp  # noqa: E402
from fo4sf.terrain.path_guard import OutputPathRefusedError  # noqa: E402


def _rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0) -> bytes:
    payload = b"".join(opp.encode_subrecord(s, d) for s, d in subs)
    if flags & opp.COMPRESSED_FLAG:
        payload = struct.pack("<I", len(payload)) + zlib.compress(payload)
    return struct.pack("<4sIIIIHH", sig, len(payload), flags, fid, 0, 576, 0) + payload


def _grup(label: bytes | int, items: list[bytes], gtype: int = 0) -> bytes:
    if isinstance(label, int):
        label = struct.pack("<I", label)
    body = b"".join(items)
    return struct.pack("<4sI4siHHHH", b"GRUP", 24 + len(body), label, gtype, 0, 0, 0, 0) + body


def _z(text: str) -> bytes:
    return text.encode("cp1252") + b"\x00"


class DlcTerrainWorldsTests(unittest.TestCase):
    def test_world_registry_dlc_terrain_built_offline_and_alias_normalized(self) -> None:
        reg = load_world_registry()
        for key in ("FarHarbor", "NukaWorld"):
            w = reg.get_world(key)
            self.assertEqual(w.status["terrain"].state, "built offline")
            self.assertEqual(w.status["water"].state, "built offline")
            self.assertEqual(w.status["terrain"].evidence, "docs/world/dlc-worlds-water-and-ground.md")
            self.assertIsNotNone(w.planned_starfield_world.planet_position)
            self.assertIsNone(w.planned_starfield_world.measured_merge_offset)

        # Pairwise separation on Mars radius (3,390 km) AND Home-planet Earth radius (6,371 km) (C11)
        cw_pos = reg.get_world("Commonwealth").planned_starfield_world.planet_position
        fh_psw = reg.get_world("FarHarbor").planned_starfield_world
        nw_psw = reg.get_world("NukaWorld").planned_starfield_world
        fh_pos = fh_psw.planet_position
        nw_pos = nw_psw.planet_position
        assert cw_pos and fh_pos and nw_pos
        self.assertEqual(fh_psw.reachability, "TEST-STATION (coc only)")
        self.assertEqual(nw_psw.reachability, "TEST-STATION (coc only)")
        self.assertEqual(fh_psw.coc_spawn, "FO4FH_FarHarborSpawn")
        self.assertEqual(nw_psw.coc_spawn, "FO4NW_NukaWorldSpawn")
        self.assertAlmostEqual(round(planet_separation_cells(cw_pos, fh_pos, MARS_RADIUS_KM), 1), 3563.1, places=1)
        self.assertAlmostEqual(round(planet_separation_cells(cw_pos, fh_pos, HOME_EARTH_RADIUS_KM), 1), 6696.4, places=1)
        self.assertAlmostEqual(round(planet_separation_cells(cw_pos, nw_pos, MARS_RADIUS_KM), 1), 4583.1, places=1)
        self.assertAlmostEqual(round(planet_separation_cells(cw_pos, nw_pos, HOME_EARTH_RADIUS_KM), 1), 8613.3, places=1)
        self.assertEqual(fh_psw.mars_separation_from_cw_cells, 3563.1)
        self.assertEqual(fh_psw.home_separation_from_cw_cells, 6696.4)
        self.assertEqual(nw_psw.mars_separation_from_cw_cells, 4583.1)
        self.assertEqual(nw_psw.home_separation_from_cw_cells, 8613.3)
        self.assertAlmostEqual(
            round(planet_separation_cells(cw_pos, fh_pos, HOME_EARTH_RADIUS_KM) / LANDING_HALF_WIDTH_CELLS, 2),
            fh_psw.landing_half_widths_home,
            places=2,
        )
        self.assertAlmostEqual(
            round(planet_separation_cells(cw_pos, nw_pos, HOME_EARTH_RADIUS_KM) / LANDING_HALF_WIDTH_CELLS, 2),
            nw_psw.landing_half_widths_home,
            places=2,
        )
        self.assertGreaterEqual(opp._latlon_distance_cells(cw_pos, fh_pos), 2000.0)
        self.assertGreaterEqual(opp._latlon_distance_cells(cw_pos, nw_pos), 2000.0)
        self.assertGreaterEqual(opp._latlon_distance_cells(fh_pos, nw_pos), 2000.0)

        # Underscore alias "built_offline" normalizes to "built offline"
        raw = json.loads(Path(ROOT / "src" / "fo4sf" / "core" / "world_registry.json").read_text(encoding="utf-8"))
        mut = copy.deepcopy(raw)
        mut["worlds"][9]["status"]["terrain"]["state"] = "built_offline"
        parsed = parse_world_registry(mut)
        self.assertEqual(parsed.get_world("FarHarbor").status["terrain"].state, "built offline")

    def test_postpatch_water_ltex_and_mars_multiworld_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = os.path.join(tmp, "stage")
            os.makedirs(os.path.join(stage, "Data", "Terrain"), exist_ok=True)
            src_dir = os.path.join(tmp, "fo4")
            os.makedirs(src_dir, exist_ok=True)

            # Synthetic 4x4 Starfield overlay plugin + compressed Mars PNDT plugin
            n = 4
            tes4 = _rec(
                b"TES4",
                0,
                [
                    (b"HEDR", struct.pack("<fII", 0.96, 30, 0x0900)),
                    (b"MAST", _z("Starfield.esm")),
                    (b"DATA", struct.pack("<Q", 0)),
                ],
                flags=0x1,
            )
            sfbk = _rec(
                b"SFBK",
                0x01000801,
                [
                    (b"EDID", _z("FO4FH_FarHarborBlock")),
                    (b"ANAM", _z("Data\\TERRAIN\\FO4FH_FarHarbor.btd")),
                    (b"DNAM", struct.pack("<2I", n, n)),
                    (b"ENAM", struct.pack("<2f", -10.0, 30.0)),
                    (b"WHGT", struct.pack("<f", -3.4028235e38)),
                ],
            )
            lctn = _rec(
                b"LCTN",
                0x01000802,
                [(b"EDID", _z("FO4FH_FarHarborLocation")), (b"FULL", _z("Commonwealth T00 (FO4 terrain)"))],
            )
            wrld = _rec(
                b"WRLD",
                0x01000803,
                [
                    (b"EDID", _z("FO4FH_FarHarbor")),
                    (b"FULL", _z("Commonwealth T00 (FO4 terrain)")),
                    (b"NAM3", struct.pack("<I", 0x18)),
                    (b"NAM4", struct.pack("<f", 0.0)),
                    (b"DNAM", struct.pack("<2f", -2048.0, -200.0)),
                ],
            )
            top_cell = _rec(b"CELL", 0x01000804, [(b"DATA", struct.pack("<I", 0x02))])
            anchor = _rec(
                b"REFR",
                0x01000800,
                [(b"EDID", _z("FO4FH_FarHarborAnchor")), (b"NAME", struct.pack("<I", 0x3B))],
                flags=0x400,
            )
            mm_ref = _rec(
                b"REFR",
                0x01000805,
                [(b"EDID", _z("FO4FH_FarHarborMapMarker")), (b"XMRK", b""), (b"FULL", _z("Red Rocket"))],
                flags=0x400,
            )
            ext_items: list[bytes] = []
            cfid = 0x01000810
            for cx in range(-2, 2):
                for cy in range(-2, 2):
                    ext_items.append(_rec(b"CELL", cfid, [(b"XCLC", struct.pack("<iiI", cx, cy, 0))]))
                    cfid += 1
            wrld_grp = _grup(
                0x01000803,
                [
                    top_cell,
                    _grup(0x01000804, [_grup(0x01000804, [anchor, mm_ref], 8)], 6),
                    _grup(struct.pack("<hh", 0, 0), [_grup(struct.pack("<hh", 0, 0), ext_items, 5)], 4),
                ],
                1,
            )
            plugin_path = os.path.join(stage, "FO4WorldFarHarbor.esm")
            Path(plugin_path).write_bytes(
                tes4 + _grup(b"SFBK", [sfbk]) + _grup(b"LCTN", [lctn]) + _grup(b"WRLD", [wrld, wrld_grp])
            )

            # Synthetic Mars plugin with compressed PNDT + inner BDST..BDED 1-byte CNAM
            fh_lat, fh_lon = og.latlon_for_offset((2500, 2500), (0.3, -1.2), (-12, -27), og.MARS_RADIUS_KM)
            mars_tes4 = _rec(
                b"TES4",
                0,
                [
                    (b"HEDR", struct.pack("<fII", 0.96, 2, 0x0800)),
                    (b"MAST", _z("Starfield.esm")),
                    (b"DATA", struct.pack("<Q", 0)),
                    (b"MAST", _z("FO4WorldFarHarbor.esm")),
                    (b"DATA", struct.pack("<Q", 0)),
                ],
                flags=0x1,
            )
            cnam_entries = struct.pack("<ddI", 0.0, -0.2, 0x0002DF8C) + struct.pack("<ddI", fh_lat, fh_lon, 0x01000803)
            pndt = _rec(
                b"PNDT",
                0x0003F59A,
                [
                    (b"EDID", _z("MarsPlanetData")),
                    (b"CNAM", cnam_entries),
                    (b"BDST", b""),
                    (b"CNAM", b"\x01"),
                    (b"BDED", b""),
                ],
                flags=opp.COMPRESSED_FLAG,
            )
            mars_path = os.path.join(stage, "FO4WorldFarHarbor_Mars.esm")
            Path(mars_path).write_bytes(mars_tes4 + _grup(b"PNDT", [pndt]))

            # Synthetic BTD & FO4 DLC plugin with flat 12.0 m height (= 840 FO4 units)
            h_m = 12.0
            hmin, hmax = -10.0, 30.0
            raw_val = int(round((h_m - hmin) / (hmax - hmin) * 65535.0))
            raw_h = np.full((n * 128, n * 128), raw_val, dtype=np.uint16)
            raw_w = np.zeros((n * 128, n * 128), dtype=np.uint16)
            quad = np.zeros((n * 2, n * 2, 8), dtype=np.uint8)
            quad[:, :, 0] = 1
            Path(stage, "Data", "Terrain", "FO4FH_FarHarbor.btd").write_bytes(
                btd.write(btd.Btd(6, hmin, hmax, [0x01000900], raw_h, raw_w, quad))
            )

            prm = {
                "plugin": "FO4WorldFarHarbor.esm",
                "water_height_m": 6.428571,
                "mars": {"plugin": "FO4WorldFarHarbor_Mars.esm", "radius_km": og.MARS_RADIUS_KM},
                "overlays": [
                    {
                        "ix": 0,
                        "iy": 0,
                        "n": n,
                        "world": "FO4FH_FarHarbor",
                        "btd_file": "Data/Terrain/FO4FH_FarHarbor.btd",
                        "cells_cw": {"x": [-2, 1], "y": [-2, 1]},
                        "planet_target_cell": [2500, 2500],
                        "latitude": fh_lat,
                        "longitude": fh_lon,
                    }
                ],
            }
            prm_path = os.path.join(stage, "overlays_params.json")
            Path(prm_path).write_text(json.dumps(prm), encoding="utf-8")

            # Synthetic FO4 DLC plugin with 9 LAND cells at 840.0 units (= 12.0 m)
            vhgt = fo4land.encode_vhgt(105.0, np.zeros((33, 33), dtype=np.int64))  # 105 * 8 = 840 units = 12.0 m
            fo4_items: list[bytes] = []
            fid = 0x000900
            for cx in range(-2, 2):
                for cy in range(-2, 2):
                    fo4_items.append(_rec(b"CELL", fid, [(b"XCLC", struct.pack("<iiI", cx, cy, 0))]))
                    fo4_items.append(_grup(fid, [_grup(fid, [_rec(b"LAND", fid + 1, [(b"VHGT", vhgt)])], 9)], 6))
                    fid += 2
            fo4_path = os.path.join(src_dir, "DLCCoast.esm")
            Path(fo4_path).write_bytes(
                _rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 20, 0x0A00))], flags=0x1)
                + _grup(
                    b"WRLD",
                    [
                        _rec(b"WRLD", 0x000B0F, [(b"EDID", _z("DLC03FarHarbor")), (b"DNAM", struct.pack("<2f", 0.0, 450.0))]),
                        _grup(0x000B0F, [_grup(struct.pack("<hh", 0, 0), [_grup(struct.pack("<hh", 0, 0), fo4_items, 5)], 4)], 1),
                    ],
                )
            )

            # Apply postpatch + 1 custom LTEX + Commonwealth extra world
            res = opp.patch_overlay_plugin(
                plugin_path,
                water_height_m=6.428571,
                world_display_name="FO4FH_FarHarbor (FO4 terrain)",
                map_marker_name="FO4FH_FarHarborArrival",
                ltex_records=[
                    {
                        "fid_local": 0x000900,
                        "edid": "FO4FH_LGrass01",
                        "bnam": "Materials\\Terrain\\FO4FH_Grass01.mat",
                    }
                ],
            )
            self.assertEqual(res["exterior_cells"], 16)
            self.assertEqual(res["ltex_added"], 1)

            mres = opp.patch_mars_plugin_extra_worlds(
                mars_path,
                prm_path,
                [
                    {
                        "plugin": "FO4TerrainCore.esm",
                        "wrld_local_fid": 0x000803,
                        "latitude": 0.3,
                        "longitude": -1.2,
                        "label": "FO4Core_Commonwealth",
                    }
                ],
            )
            self.assertEqual(mres["added_entries"], 1)

            # Verify inner BDST..BDED 1-byte CNAM stayed untouched!
            mplug = opp.RawPlugin.read(mars_path)
            pndt_after = mplug.items[0].children[0]
            body_cnam = [d for s, d in pndt_after.fields() if s == b"CNAM" and len(d) == 1]
            self.assertEqual(body_cnam, [b"\x01"])

            vrep = opp.verify_dlc_terrain_stage(stage, [fo4_path], "DLC03FarHarbor", n_probes=5, min_gap_cells=2000)
            self.assertEqual(vrep["reachability"], "TEST-STATION (coc only)")
            self.assertEqual(vrep["wrld_count"], 1)
            self.assertEqual(vrep["water_exterior_cells_verified"], 16)
            self.assertLess(vrep["max_probe_abs_error_m"], 0.01)
            self.assertGreaterEqual(vrep["nearest_other_world_distance_cells"], 2000.0)
            self.assertGreater(
                vrep["home_earth_nearest_other_world_distance_cells"],
                vrep["nearest_other_world_distance_cells"],
            )

            # R4 path guard refuses fake worktree
            fake_wt = os.path.join(tmp, "wt")
            os.makedirs(os.path.join(fake_wt, ".git"), exist_ok=True)
            with self.assertRaises(OutputPathRefusedError):
                opp.patch_overlay_plugin(os.path.join(fake_wt, "bad.esm"), water_height_m=1.0)


if __name__ == "__main__":
    unittest.main()
