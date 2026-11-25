"""Offline tests for Round 14 Task 3 (FO3/NV world rows, Earth host registration, lore plan, Border switch)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))

import make_home_planet  # noqa: E402
from fo4sf.core import world_registry  # noqa: E402
from fo4sf.planet import esm, home_planet_spec as hspec  # noqa: E402
from tests.test_planet_home import _build_synthetic_starfield_data  # noqa: E402


def _earth_sep_cells(a: tuple[float, float], b: tuple[float, float]) -> float:
    d = 2.0 * math.asin(
        math.sqrt(
            math.sin((b[0] - a[0]) / 2.0) ** 2
            + math.cos(a[0]) * math.cos(b[0]) * math.sin((b[1] - a[1]) / 2.0) ** 2
        )
    )
    return 6371000.0 * d / 100.0


def _write_pilot_overlay_esm(path: Path, world_edid: str, lctn_edid: str, sfbk_edid: str) -> None:
    """Write a synthetic host=None pilot overlay ESM (masters=['Starfield.esm'] only)."""
    pw = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    own = pw.own
    pw.add(esm.Record(b"SFBK", own(0x801), [(b"EDID", esm.zbytes(sfbk_edid))]))
    pw.add(
        esm.Record(
            b"LCTN",
            own(0x802),
            [
                (b"EDID", esm.zbytes(lctn_edid)),
                (b"FULL", esm.zbytes(world_edid)),
                (b"KSIZ", struct.pack("<I", 1)),
                (b"KWDA", struct.pack("<I", 0x2CA99D)),
                (b"DATA", b"\x00" * 8),
                (b"PNAM", struct.pack("<I", 0x01B736)),
            ],
        )
    )
    pw.add(
        esm.Record(
            b"WRLD",
            own(0x803),
            [
                (b"EDID", esm.zbytes(world_edid)),
                (b"BFCB", esm.zbytes("BGSWorldSpaceOverlay_Component")),
                (b"SNAM", struct.pack("<i", 0)),
                (b"PNAM", struct.pack("<i", 4)),
                (b"BNAM", struct.pack("<I", own(0x801))),
                (b"BFCE", b""),
                (b"XLCN", struct.pack("<I", own(0x802))),
                (b"BNAM", struct.pack("<I", 0x2A3777)),
                (b"DATA", b"\x01"),
                (b"FNAM", b"\x00"),
            ],
        )
    )
    pw.write(str(path), compress=False)


class Round14Fo3NvWorldsTests(unittest.TestCase):
    def test_registry_fo3_nv_fields_and_commonwealth_unmoved(self) -> None:
        reg = world_registry.load_world_registry()
        cw = reg.get_world("Commonwealth")
        self.assertEqual(list(cw.planned_starfield_world.planet_position), [0.3, -1.2])
        self.assertEqual(list(cw.planned_starfield_world.measured_merge_offset), [-1200.0, -2700.0])

        fo3 = reg.get_world("CapitalWasteland")
        fnv = reg.get_world("MojaveWasteland")
        self.assertEqual(fo3.source_worldspace.edid, "Wasteland")
        self.assertEqual(fnv.source_worldspace.edid, "WastelandNV")

        for row, plugin, code, spawn in (
            (fo3, "FO4CapitalWasteland.esm", 2, "FO3Core_Vault101ExitSpawn"),
            (fnv, "FO4Mojave.esm", 3, "FNVCore_GoodspringsSpawn"),
        ):
            psw = row.planned_starfield_world
            self.assertEqual(psw.plugin, plugin)
            self.assertEqual(psw.tile_cells, 64)
            self.assertEqual(psw.cell_count, 4096)
            self.assertEqual(psw.host_planet, "FO4SFHomePlanet")
            self.assertIsNone(psw.measured_merge_offset)
            self.assertEqual(psw.pipboy_plugin_code, code)
            self.assertEqual(psw.reachability, "TEST-STATION (coc only)")
            self.assertEqual(psw.coc_spawn, spawn)
            self.assertIsNotNone(psw.planet_position)
            self.assertGreater(_earth_sep_cells((0.3, -1.2), psw.planet_position), 45.0)

        self.assertGreater(
            _earth_sep_cells(fo3.planned_starfield_world.planet_position, fnv.planned_starfield_world.planet_position),
            45.0,
        )

    def test_home_registration_accepts_pilot_and_canonical_fo3_nv_worlds(self) -> None:
        self.assertEqual(hspec.WORLD_DISPLAY_NAMES["CapitalWasteland"], "Capital Wasteland")
        self.assertEqual(hspec.WORLD_DISPLAY_NAMES["MojaveWasteland"], "Mojave Wasteland")

        for label, cw_edid, nv_edid in (
            ("pilots", "FO3Core_CapitalWasteland", "FNVCore_Mojave"),
            ("canonical", "FO4CW_CapitalWasteland", "FO4NV_MojaveWasteland"),
        ):
            with self.subTest(variant=label):
                with tempfile.TemporaryDirectory(prefix="fo4sf-r14-fo3nv-") as tmp:
                    root = Path(tmp)
                    data_dir = root / "sf_data"
                    _build_synthetic_starfield_data(data_dir)
                    pilots_dir = root / "pilots"
                    pilots_dir.mkdir()
                    fo3_esm = pilots_dir / "FO4CapitalWasteland.esm"
                    fnv_esm = pilots_dir / "FO4Mojave.esm"
                    _write_pilot_overlay_esm(fo3_esm, cw_edid, "FO3Core_CWLoc", "FO3Core_CWBlock")
                    _write_pilot_overlay_esm(fnv_esm, nv_edid, "FNVCore_NVLoc", "FNVCore_NVBlock")

                    fo3_sha = hashlib.sha256(fo3_esm.read_bytes()).hexdigest()
                    fnv_sha = hashlib.sha256(fnv_esm.read_bytes()).hexdigest()

                    stage_dir = root / "stage_out"
                    rc = make_home_planet.main(
                        [
                            "stage",
                            "--data",
                            str(data_dir),
                            "--out",
                            str(stage_dir),
                            "--worlds",
                            "Commonwealth,CapitalWasteland,MojaveWasteland",
                            "--world-plugin-dir",
                            str(pilots_dir),
                        ]
                    )
                    self.assertEqual(rc, 0)
                    self.assertEqual(hashlib.sha256(fo3_esm.read_bytes()).hexdigest(), fo3_sha)
                    self.assertEqual(hashlib.sha256(fnv_esm.read_bytes()).hexdigest(), fnv_sha)

                    rc_chk = make_home_planet.main(
                        [
                            "check",
                            "--stage",
                            str(stage_dir),
                            "--data",
                            str(data_dir),
                            "--world-plugin-dir",
                            str(pilots_dir),
                        ]
                    )
                    self.assertEqual(rc_chk, 0)

                    plan = json.loads((stage_dir / "plan.json").read_text(encoding="utf-8"))
                    chk = json.loads((stage_dir / "offline_check.json").read_text(encoding="utf-8"))
                    self.assertEqual(plan["worlds"], ["Commonwealth", "CapitalWasteland", "MojaveWasteland"])
                    self.assertEqual(len(chk["registration"]["worlds"]), 3)
                    self.assertIn("FO4CapitalWasteland.esm", chk["registration"]["masters"])
                    self.assertIn("FO4Mojave.esm", chk["registration"]["masters"])

    def test_border_registered_earth_worlds_switch_default_off_and_registered_list(self) -> None:
        psc = (ROOT / "scripts" / "mapmarkers" / "FO4SF_MapMarkers.psc").read_text(encoding="utf-8")
        self.assertIn("bool Property BorderRegisteredEarthWorlds = False Auto", psc)
        self.assertIn("elseif BorderRegisteredEarthWorlds && c != None && IsRegisteredEarthWorldCell(c)", psc)
        for plug in (
            "FO4TerrainCore.esm",
            "FO4WorldFarHarbor.esm",
            "FO4WorldNukaWorld.esm",
            "FO4CapitalWasteland.esm",
            "FO4Mojave.esm",
        ):
            self.assertIn(f'"{plug}"', psc)

    def test_lore_placement_and_host_routes_doc_complete(self) -> None:
        doc = ROOT / "docs" / "world" / "earth-lore-placement-plan.md"
        self.assertTrue(doc.is_file())
        txt = doc.read_text(encoding="utf-8")
        for token in (
            "Boston",
            "Washington, DC",
            "Las Vegas",
            "Do NOT move the Commonwealth",
            "FO3Core_CapitalWasteland",
            "FNVCore_Mojave",
            "FO4TerrainCore_Home.esm",
            "TerrainOverlays",
            "BorderRegisteredEarthWorlds",
        ):
            self.assertIn(token, txt)


if __name__ == "__main__":
    unittest.main()
