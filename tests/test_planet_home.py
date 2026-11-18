"""Offline synthetic unit tests for `W2`, `W3`, `W4`, `WL1`, `WL2`, and `R4`
(`src/fo4sf/planet/home_planet_spec.py`, `src/fo4sf/planet/biom.py`, `scripts/planet/make_home_planet.py`,
`scripts/terrain/sf_location_census.py`, and `docs/world/three-way-study.md`).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for sub in ("src", "scripts/planet", "scripts/terrain"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4_world_census import CensusPathError  # noqa: E402
from fo4sf.planet import biom, esm, home_planet_spec as hspec, probe, records, wb_records  # noqa: E402
import make_home_planet  # noqa: E402
import sf_location_census  # noqa: E402

# R12 control SHA-256 pins from Round-1 head b7dc7f52 (--control-b7dc7f52 preset)
B7DC7F52_HOME_MASTER_SHA256 = "513a0a1ef0bfa4bde6c83f9611ba1715a2081da0c8d2a0dd4be272c768291f5c"
B7DC7F52_HOME_REG_SHA256 = "31f180babafa7e7c57a3d1aef888b558cd54735c9e417cbac643965aa5412596"
B7DC7F52_HOME_BIOM_SHA256 = "76cf7f10696c8eab417206f57e3d797a271e7bd5a42336134f2a3b2c1d967a3b"

# parity not applicable: ordered by C9 (non-colliding PNDT ANAM 'fo4sf_home_earth' on Starfield-patterned control)
C9_DEFAULT_HOME_MASTER_SHA256 = "4a206130c7a2aefa04295359ce1b6fb91604498a86ce695e789373d4f1077b0b"
C9_DEFAULT_HOME_REG_SHA256 = "53a52534c0497bb20a392eb835a19fafeffe5d19c8140d110cf221073c091a64"
C9_DEFAULT_HOME_BIOM_SHA256 = "76cf7f10696c8eab417206f57e3d797a271e7bd5a42336134f2a3b2c1d967a3b"

# parity not applicable: ordered by WB1, WB2, WB3 (default weather, sky, FO4 ground LTEX, smallest PTST, WB3 overrides)
WB1_WB3_DEFAULT_HOME_MASTER_SHA256 = "c09fe96cb47fc6c382bb334f832703f92b6e256d32e9b7e51747d44c8727af7c"
WB1_WB3_DEFAULT_HOME_REG_SHA256 = "41d4f384a1f0ff654ef411c5acf011d9685becb356d15c5918e3d3478226f6d6"
WB1_WB3_DEFAULT_HOME_BIOM_SHA256 = "76cf7f10696c8eab417206f57e3d797a271e7bd5a42336134f2a3b2c1d967a3b"
WB1_WB3_DEFAULT_HOME_MAT_SHA256 = "f325b12538068a66a48dbc9996ebbf5969f8005d9d1cd11d636d1bfc293378a4"


def _build_synthetic_starfield_data(data_dir: Path) -> Path:
    """Create a synthetic `Data/Starfield.esm` and `Data/FO4TerrainCore.esm` with zero game files read."""
    data_dir.mkdir(parents=True, exist_ok=True)
    sf_path = data_dir / "Starfield.esm"
    w = esm.PluginWriter([], esm.ESM)

    kywds = [
        (0x00149F, "LocTypeStarSystem"),
        (0x0014A0, "LocTypePlanet"),
        (0x016010, "LocTypeMoon"),
        (0x070A54, "LocTypeMajorOrbital"),
        (0x016503, "LocTypeSurface"),
        (0x016504, "LocTypeOrbit"),
        (0x2CA99D, "LocTypeOverlay"),
        (0x121A19, "Star_Class_G"),
        (0x295EA4, "PlanetAtmosphereType05O2"),
        (0x295EC0, "PlanetPressure02Terrestrial"),
        (0x295EC5, "PlanetTemperature03Temperate"),
        (0x295EBC, "PlanetGravity01Terrestrial"),
        (0x295EB8, "PlanetWaterQuality01Safe"),
        (0x295ECA, "PlanetWaterAbundance02Terrestrial"),
        (0x295EAF, "PlanetFaunaAbundance00None"),
        (0x295EB4, "PlanetFloraAbundance00None"),
        (0x295ED0, "PlanetType07Rock"),
        (0x290FCD, "PlanetMagnetosphereType04Strong"),
        (0x11D575, "LocTypeNoPCMScanTreeContent"),
        (0x295EA8, "PlanetAtmosphereType01CO2"),
        (0x295EC1, "PlanetPressure01Thin"),
        (0x295EC6, "PlanetTemperature02Cold"),
        (0x1EF941, "LocTypeNoHumanPresence"),
        (0x1984BD, "PCM_OverlayExclusionZone"),
        (0x0C21AD, "PCM_OverlayExclusionZone_HumanLocations"),
        (0x2194F4, "LocTypeNoPCMCreatureContent"),
        (0x2253D1, "LocTypeSENotAllowed"),
    ]
    for fid, edid in kywds:
        w.add(esm.Record(b"KYWD", fid, [(b"EDID", esm.zbytes(edid))]))

    w.add(esm.Record(b"LCRT", 0x02271F, [(b"EDID", esm.zbytes("MapMarkerRefType"))]))
    w.add(esm.Record(b"GLOB", 0x2EDD3B, [(b"EDID", esm.zbytes("PCM_BiomeDensity_None"))]))
    w.add(esm.Record(b"LTEX", 0x1235C2, [(b"EDID", esm.zbytes("LDirtFootprints01"))]))
    w.add(esm.Record(b"CLMT", 0x24E982, [(b"EDID", esm.zbytes("ClimateUniqueNewAtlantis"))]))
    w.add(esm.Record(b"CLMT", 0x00015F, [(b"EDID", esm.zbytes("DefaultClimate"))]))
    w.add(esm.Record(b"ATMO", 0x00C010, [(b"EDID", esm.zbytes("ATMO_Jemison"))]))
    w.add(esm.Record(b"ATMO", 0x00C9D1, [(b"EDID", esm.zbytes("ATMO_Earth"))]))
    w.add(esm.Record(b"SFTR", 0x1B6C63, [(b"EDID", esm.zbytes("EarthSurfaceTree"))]))
    w.add(esm.Record(b"PTST", 0x23DE7E, [(b"EDID", esm.zbytes("PatternStyleHillsRockyFieldsRocky"))]))
    w.add(esm.Record(b"PTST", 0x23DECE, [(b"EDID", esm.zbytes("PatternStyleFieldsHillsFieldsFlat"))]))
    w.add(esm.Record(b"PTST", 0x0EEA98, [(b"EDID", esm.zbytes("PatternStyleFieldsMixed"))]))
    w.add(esm.Record(b"MATT", 0x012F3E, [(b"EDID", esm.zbytes("MaterialDirtlSand"))]))
    w.add(esm.Record(b"MUSC", 0x01BA72, [(b"EDID", esm.zbytes("_NONE"))]))
    w.add(esm.Record(b"SUNP", 0x134249, [(b"EDID", esm.zbytes("SunPresetTypeG2"))]))

    w.add(esm.Record(b"LCTN", 0x01A53A, [(b"EDID", esm.zbytes("Universe"))]))
    w.add(records.new_location(0x061527, "SSol", "Sol", [0x00149F], 0x01A53A, 0, 0))
    w.add(records.new_location(0x01B736, "SSol_PMars_Surface", "Mars", [0x016503], 0x061527, 0, 4))

    w.add(
        esm.Record(
            b"STDT",
            0x05E5CB,
            [
                (b"EDID", esm.zbytes("SolStar")),
                (b"ANAM", esm.zbytes("Sol")),
                (b"BNAM", struct.pack("<3f", 0.0, 0.0, 0.0)),
                (b"DNAM", struct.pack("<I", 0)),
                (b"ENAM", struct.pack("<I", 0xFFEDFCFC)),
            ],
        )
    )
    w.add(
        esm.Record(
            b"PNDT",
            0x03F59A,
            [
                (b"EDID", esm.zbytes("MarsPlanetData")),
                (b"BDST", b""),
                (b"ANAM", esm.zbytes("Mars")),
                (b"GNAM", struct.pack("<III", 0, 0, 4)),
                (b"BDED", b""),
            ],
        )
    )
    w.write(str(sf_path), compress=False)

    # Synthetic FO4TerrainCore.esm with SFBK 0x801, LCTN 0x802 (carrying LCSR), WRLD 0x803
    cw = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    own = cw.own
    cw.add(esm.Record(b"SFBK", own(0x801), [(b"EDID", esm.zbytes("FO4Core_CommonwealthBlock"))]))
    lcsr = struct.pack("<5I", 0x0002271F, own(0x80A), own(0x803), 0x00000000, 0xFFFFFFFF)
    cw.add(
        esm.Record(
            b"LCTN",
            own(0x802),
            [
                (b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")),
                (b"LCSR", lcsr),
                (b"FULL", esm.zbytes("Commonwealth 00")),
                (b"KSIZ", struct.pack("<I", 1)),
                (b"KWDA", struct.pack("<I", 0x2CA99D)),
                (b"DATA", records.DEFAULT_LOCATION_DATA),
                (b"PNAM", struct.pack("<I", 0x01B736)),
                (b"XNAM", struct.pack("<i", -1)),
                (b"YNAM", struct.pack("<i", -3)),
            ],
        )
    )
    cw.add(
        esm.Record(
            b"WRLD",
            own(0x803),
            [
                (b"EDID", esm.zbytes("FO4Core_Commonwealth")),
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
    cw.write(str(data_dir / "FO4TerrainCore.esm"), compress=False)
    return sf_path


class HomePlanetSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="fo4sf-home-test-")
        self.root = Path(self.tmp.name)
        self.data_dir = self.root / "mock_sf_data"
        self.sf_path = _build_synthetic_starfield_data(self.data_dir)
        self.out_root = self.root / "safe_out"
        self.out_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_w2_w3_w4_stage_check_and_core_byte_identity(self) -> None:
        core_path = self.data_dir / "FO4TerrainCore.esm"
        core_sha_before = hashlib.sha256(core_path.read_bytes()).hexdigest()

        stage_dir = self.out_root / "home-stage"
        rc = make_home_planet.main(
            ["stage", "--data", str(self.data_dir), "--out", str(stage_dir), "--sky", "ATMO_Earth", "--temp", "16.5"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(hashlib.sha256(core_path.read_bytes()).hexdigest(), core_sha_before)

        rc_chk = make_home_planet.main(["check", "--stage", str(stage_dir), "--data", str(self.data_dir)])
        self.assertEqual(rc_chk, 0)

        # W2: verify every spec entry has a source and zero hazard keywords / zero PCCC exist
        for table in (hspec.STAR_FIELD_SPEC, hspec.PLANET_FIELD_SPEC, hspec.BIOM_FIELD_SPEC):
            self.assertTrue(len(table) >= 6)
            for row in table:
                self.assertTrue(row.get("subrecord"))
                self.assertTrue(row.get("source"))

        with esm.Plugin(str(stage_dir / hspec.HOME_MASTER)) as hm:
            pndt = next(r for r in hm.records("PNDT"))
            stdt = next(r for r in hm.records("STDT"))
            biom_rec = next(r for r in hm.records("BIOM"))
            self.assertIsNone(pndt.get(b"PCCC"))
            self.assertIsNone(stdt.get(b"PCCC"))
            phys = records.orbital(pndt)
            self.assertAlmostEqual(phys["surface_gravity"], 1.0, places=4)
            self.assertAlmostEqual(phys["radius_km"], 6371.0, places=2)
            self.assertAlmostEqual(phys["mean_orbit"], 149598000.0, places=1)
            self.assertAlmostEqual(phys["rotational_velocity"], 1.0, places=4)
            self.assertAlmostEqual(phys["temp"], 16.5, places=3)
            inam = records.body_get(pndt.subs, b"INAM")
            self.assertEqual(struct.unpack_from("<I", inam, 0)[0], 0x00C9D1)  # ATMO_Earth selected
            self.assertEqual(esm.zstring(records.body_get(pndt.subs, b"ANAM")), "fo4sf_home_earth")
            self.assertEqual(esm.zstring(probe.component_fields(pndt, "TESFullName_Component")["FULL"]), "Earth")
            self.assertEqual(biom_rec.all(b"GNAM"), [])
            self.assertEqual(biom_rec.all(b"NAM1"), [])

        # W3: verify FO4TerrainCore_Home.esm has 3 records and remapped LCSR & SFBK to 0x02XXXXXX
        with esm.Plugin(str(stage_dir / hspec.HOME_REGISTRATION)) as reg:
            self.assertEqual(reg.masters, ["Starfield.esm", "FO4SFHome.esm", "FO4TerrainCore.esm"])
            pndts = list(reg.records("PNDT"))
            lctns = list(reg.records("LCTN"))
            wrlds = [
                reg.record_at(it[1])
                for st, en in reg.groups.get("WRLD", [])
                for it in reg.walk(st, en, groups=set())
                if it[0] == "REC"
            ]
            self.assertEqual((len(pndts), len(wrlds), len(lctns)), (1, 1, 1))
            lcrt, refr, wrld_fid, _grid, tail = struct.unpack("<5I", lctns[0].get(b"LCSR"))
            self.assertEqual((lcrt, refr, wrld_fid, tail), (0x0002271F, 0x0200080A, 0x02000803, 0xFFFFFFFF))
            ov = probe.component_fields(wrlds[0], "BGSWorldSpaceOverlay_Component")
            self.assertEqual(struct.unpack("<I", ov["BNAM"])[0], 0x02000801)
            self.assertEqual(struct.unpack("<I", probe.top_level(wrlds[0], b"BNAM"))[0], 0x01000806)

        # W4 + C9: verify BOTH .biom files exist under fo4sf_home_earth.biom and BOTH carry TEST-STATION
        plan = make_home_planet.load_plan(str(stage_dir))
        self.assertEqual(plan["body_name"], "fo4sf_home_earth")
        self.assertEqual(plan["planet_name"], "Earth")
        self.assertNotIn("VERIFIED_ENGINE_ANAM_PATH", set(plan["biome_map"]["path_status"].values()))
        for rel in (
            "Data/PlanetData/BiomeMaps/fo4sf_home_earth.biom",
            "Data/PlanetData/BiomeMaps/fo4sfhome.esm/fo4sf_home_earth.biom",
        ):
            self.assertEqual(plan["biome_map"]["path_status"][rel], "TEST-STATION")
            bpath = stage_dir / Path(*rel.split("/"))
            self.assertTrue(bpath.is_file(), rel)
            self.assertEqual(bpath.stat().st_size, 655406)

    def test_r12_b7dc7f52_earth_control_and_wb1_wb3_default_pinned_sha256(self) -> None:
        # 1. Named b7dc7f52 control preset (--control-b7dc7f52) reproduces exact Round-1 bytes
        ctrl_dir = self.out_root / "r12-b7dc7f52-control"
        self.assertEqual(
            make_home_planet.main(
                ["stage", "--data", str(self.data_dir), "--out", str(ctrl_dir), "--control-b7dc7f52"]
            ),
            0,
        )
        self.assertEqual(
            hashlib.sha256((ctrl_dir / hspec.HOME_MASTER).read_bytes()).hexdigest(),
            B7DC7F52_HOME_MASTER_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((ctrl_dir / hspec.HOME_REGISTRATION).read_bytes()).hexdigest(),
            B7DC7F52_HOME_REG_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((ctrl_dir / "Data" / "PlanetData" / "BiomeMaps" / "earth.biom").read_bytes()).hexdigest(),
            B7DC7F52_HOME_BIOM_SHA256,
        )

        # 2. C9 control (fo4sf_home_earth with Starfield-patterned control switches)
        c9_dir = self.out_root / "r12-c9-control"
        self.assertEqual(
            make_home_planet.main(
                [
                    "stage",
                    "--data",
                    str(self.data_dir),
                    "--out",
                    str(c9_dir),
                    "--climate",
                    "ClimateUniqueNewAtlantis",
                    "--sky",
                    "ATMO_Jemison",
                    "--ground-ltex",
                    "LDirtFootprints01",
                    "--pattern",
                    "PatternStyleHillsRockyFieldsRocky",
                    "--surface-tree",
                    "EarthSurfaceTree",
                    "--wb3-mode",
                    "passthrough",
                ]
            ),
            0,
        )
        self.assertEqual(
            hashlib.sha256((c9_dir / hspec.HOME_MASTER).read_bytes()).hexdigest(),
            C9_DEFAULT_HOME_MASTER_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((c9_dir / hspec.HOME_REGISTRATION).read_bytes()).hexdigest(),
            C9_DEFAULT_HOME_REG_SHA256,
        )

        # 3. parity not applicable: ordered by WB1, WB2, WB3 (new default build)
        def_dir = self.out_root / "r12-wb1-wb3-default"
        self.assertEqual(
            make_home_planet.main(["stage", "--data", str(self.data_dir), "--out", str(def_dir)]),
            0,
        )
        self.assertEqual(
            hashlib.sha256((def_dir / hspec.HOME_MASTER).read_bytes()).hexdigest(),
            WB1_WB3_DEFAULT_HOME_MASTER_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((def_dir / hspec.HOME_REGISTRATION).read_bytes()).hexdigest(),
            WB1_WB3_DEFAULT_HOME_REG_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (def_dir / "Data" / "PlanetData" / "BiomeMaps" / "fo4sf_home_earth.biom").read_bytes()
            ).hexdigest(),
            WB1_WB3_DEFAULT_HOME_BIOM_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (def_dir / "Data" / "materials" / "terrain" / "FO4SFHomeGroundDirt01.mat").read_bytes()
            ).hexdigest(),
            WB1_WB3_DEFAULT_HOME_MAT_SHA256,
        )

    def test_w2_system_id_bumps_when_preferred_id_is_taken_in_data(self) -> None:
        clash = esm.PluginWriter(["Starfield.esm"], esm.ESM)
        clash.add(
            esm.Record(
                b"STDT",
                clash.own(0x800),
                [
                    (b"EDID", esm.zbytes("OtherModStar")),
                    (b"ANAM", esm.zbytes("Other")),
                    (b"BNAM", struct.pack("<3f", 20.0, 20.0, 20.0)),
                    (b"DNAM", struct.pack("<I", hspec.DEFAULT_HOME_SYSTEM_ID)),
                    (b"ENAM", struct.pack("<I", 0xFFFFFFFF)),
                ],
            )
        )
        clash.write(str(self.data_dir / "OtherStarMod.esm"), compress=False)

        stage_dir = self.out_root / "bumped-stage"
        self.assertEqual(
            make_home_planet.main(["stage", "--data", str(self.data_dir), "--out", str(stage_dir)]),
            0,
        )
        plan = make_home_planet.load_plan(str(stage_dir))
        self.assertNotEqual(int(plan["system_id"], 16), hspec.DEFAULT_HOME_SYSTEM_ID)

    def test_w3_refuses_duplicate_pndt_or_lctn_overrides_across_plugin_set(self) -> None:
        stage_dir = self.out_root / "dup-check-stage"
        self.assertEqual(
            make_home_planet.main(["stage", "--data", str(self.data_dir), "--out", str(stage_dir)]),
            0,
        )
        reg_path = str(stage_dir / hspec.HOME_REGISTRATION)

        # Second plugin overriding FO4TerrainCore.esm LCTN 0x000802
        other_lctn = self.out_root / "ConflictingMarkers.esm"
        w1 = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
        w1.add(records.new_location(0x01000802, "FO4Core_CommonwealthLocation", "CW", [0x2CA99D], 0x01B736, 0, 4))
        w1.write(str(other_lctn), compress=False)
        probs_lctn = hspec.check_no_duplicate_overrides([reg_path, str(other_lctn)])
        self.assertEqual(len(probs_lctn), 1)
        self.assertIn("duplicate LCTN override of fo4terraincore.esm:000802", probs_lctn[0])

        # Second plugin overriding FO4SFHome.esm PNDT 0x000805
        other_pndt = self.out_root / "ConflictingPlanetReg.esm"
        w2 = esm.PluginWriter(["Starfield.esm", "FO4SFHome.esm"], esm.ESM)
        w2.add(
            esm.Record(
                b"PNDT",
                0x01000805,
                [(b"EDID", esm.zbytes("EarthPlanetData")), (b"BDST", b""), (b"ANAM", esm.zbytes("Earth")), (b"BDED", b"")],
            )
        )
        w2.write(str(other_pndt), compress=False)
        probs_pndt = hspec.check_no_duplicate_overrides([reg_path, str(other_pndt)])
        self.assertEqual(len(probs_pndt), 1)
        self.assertIn("duplicate PNDT override of fo4sfhome.esm:000805", probs_pndt[0])

    def test_wl1_variants_stage_and_census_verifies_exact_keywords(self) -> None:
        wl1_dir = self.out_root / "wl1"
        rc = make_home_planet.main(["stage-wl1", "--data", str(self.data_dir), "--out", str(wl1_dir)])
        self.assertEqual(rc, 0)
        summary = json.loads((wl1_dir / "wl1_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(len(summary["variants"]), 7)
        for v in summary["variants"]:
            want = {k: (k in v["lever_keywords"]) for k in hspec.LEVER_KEYWORD_EDIDS}
            self.assertEqual(v["home_surface_location"]["levers"], want)
            self.assertEqual(v["registration_locations"][0]["levers"], want)

    def test_wl2_plugin_sets_only_fnam_bits_approved_in_study_doc(self) -> None:
        study_text = (ROOT / "docs" / "world" / "three-way-study.md").read_text(encoding="utf-8")
        section = study_text.split("## 4. Worldspace `FNAM` Flag Bits (`WL2`)", 1)[1].split("\n## ", 1)[0]
        approved_mask = 0
        for line in section.splitlines():
            if not line.startswith("|") or "Set in `FO4TerrainCore_Home.esm`?" in line or line.startswith("|---"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 5 and "yes" in cols[4].lower():
                m = re.search(r"0x([0-9A-Fa-f]+)", cols[0])
                if m:
                    approved_mask |= int(m.group(1), 16)

        self.assertEqual(approved_mask, 0x00)
        self.assertEqual(hspec.ALLOWED_WRLD_FNAM_BITS, approved_mask)

        stage_dir = self.out_root / "wl2-stage"
        make_home_planet.main(["stage", "--data", str(self.data_dir), "--out", str(stage_dir)])
        inspected = sf_location_census.inspect_host_plugins(
            str(self.sf_path),
            home_esm=str(stage_dir / hspec.HOME_MASTER),
            registration_esm=str(stage_dir / hspec.HOME_REGISTRATION),
        )
        for wrld in inspected["our_registration"]["worlds"]:
            self.assertEqual(wrld["fnam_int"] & ~approved_mask, 0)

        # Verify unproven bits are rejected by builder
        dummy_wrld = esm.Record(b"WRLD", 0x01000803, [(b"EDID", esm.zbytes("W")), (b"FNAM", b"\x00")])
        for bad_bit in (0x01, 0x02, 0x04):
            with self.assertRaises(records.PlanetError):
                hspec._remap_wrld_override(dummy_wrld, 1, 2, 100, 1, 0x01000806, fnam_flags=bad_bit)

    def test_r4_refuses_output_inside_git_worktree_or_game_folder(self) -> None:
        # Inside Git worktree -> exit 1
        in_repo = ROOT / "build_forbidden_home_stage"
        self.assertEqual(
            make_home_planet.main(["stage", "--data", str(self.data_dir), "--out", str(in_repo)]),
            1,
        )
        self.assertFalse(in_repo.exists())

        # Inside game installation directory (where Starfield.exe + Data/Starfield.esm sit) -> exit 1
        mock_game_root = self.root / "mock_game_install"
        mock_game_data = mock_game_root / "Data"
        _build_synthetic_starfield_data(mock_game_data)
        (mock_game_root / "Starfield.exe").write_bytes(b"MZ")
        in_game = mock_game_root / "staged_inside_game"
        self.assertEqual(
            make_home_planet.main(["stage", "--data", str(mock_game_data), "--out", str(in_game)]),
            1,
        )
        self.assertFalse(in_game.exists())

    def test_c1_home_world_install_cli_help_runs_with_clean_pythonpath_and_card1_uses_dir(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        script = str(ROOT / "scripts" / "planet" / "home_world_install.py")

        for extra_args in (
            ["--help"],
            ["install", "--help"],
            ["uninstall", "--help"],
            ["undo", "--help"],
            ["status", "--help"],
            ["order", "--help"],
            ["active", "--help"],
        ):
            proc = subprocess.run(
                [sys.executable, "-B", script, *extra_args],
                cwd=str(self.root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=f"{extra_args}: {proc.stderr}")
            self.assertIn("--dir", proc.stdout)
            self.assertIn("--starfield", proc.stdout)
            self.assertIn("--prepacked", proc.stdout)

        card_text = (ROOT / "docs" / "testing" / "home-world-lead-card.md").read_text(encoding="utf-8")
        card1 = card_text.split("## Card 1", 1)[1].split("\n## Card 2", 1)[0]
        self.assertIn("home_world_install.py install --dir <home-stage> --starfield <game-dir>", card1)
        self.assertNotIn("home_world_install.py install --stage", card1)

    def test_c3_stage_with_map_markers_merges_lcsr_adds_master_and_pins_sha256(self) -> None:
        mm_path = self.data_dir / "FO4SFMapMarkers.esm"
        mm_w = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
        # Core row (refr in master[1] = FO4TerrainCore.esm) + two extra rows owned by FO4SFMapMarkers.esm (self_index = 2)
        core_row = struct.pack("<5I", 0x0002271F, 0x0100080A, 0x01000803, 0x00000000, 0xFFFFFFFF)
        extra_row_1 = struct.pack("<5I", 0x0002271F, 0x02000800, 0x01000803, 0x0005FFFE, 0xFFFFFFFF)
        extra_row_2 = struct.pack("<5I", 0x00009105, 0x02000801, 0x01000803, 0x0006FFFD, 0xFFFFFFFF)
        mm_w.add(
            esm.Record(
                b"LCTN",
                0x01000802,
                [
                    (b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")),
                    (b"LCSR", core_row + extra_row_1 + extra_row_2),
                    (b"FULL", esm.zbytes("Commonwealth 00")),
                    (b"KSIZ", struct.pack("<I", 1)),
                    (b"KWDA", struct.pack("<I", 0x2CA99D)),
                    (b"DATA", records.DEFAULT_LOCATION_DATA),
                    (b"PNAM", struct.pack("<I", 0x01B736)),
                    (b"XNAM", struct.pack("<i", -1)),
                    (b"YNAM", struct.pack("<i", -3)),
                ],
            )
        )
        mm_w.add(
            esm.Record(
                b"WRLD",
                0x01000803,
                [
                    (b"EDID", esm.zbytes("FO4Core_Commonwealth")),
                    (b"BFCB", esm.zbytes("BGSWorldSpaceOverlay_Component")),
                    (b"SNAM", struct.pack("<i", 0)),
                    (b"PNAM", struct.pack("<i", 4)),
                    (b"BNAM", struct.pack("<I", 0x01000801)),
                    (b"BFCE", b""),
                    (b"XLCN", struct.pack("<I", 0x01000802)),
                    (b"BNAM", struct.pack("<I", 0x2A3777)),
                    (b"DATA", b"\x01"),
                    (b"FNAM", b"\x00"),
                ],
            )
        )
        mm_w.write(str(mm_path), compress=False)
        mm_sha = hashlib.sha256(mm_path.read_bytes()).hexdigest()

        stage_dir = self.out_root / "home-stage-with-mm"
        rc = make_home_planet.main(
            [
                "stage",
                "--data",
                str(self.data_dir),
                "--out",
                str(stage_dir),
                "--map-markers",
                str(mm_path),
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(hashlib.sha256(mm_path.read_bytes()).hexdigest(), mm_sha)

        plan = make_home_planet.load_plan(str(stage_dir))
        self.assertEqual(plan["map_markers_plugin"], "FO4SFMapMarkers.esm")
        self.assertEqual(plan["map_markers_sha256"], mm_sha)
        self.assertEqual(plan["biome_profile"], "our-weather-sky-fo4-ground")

        with esm.Plugin(str(stage_dir / hspec.HOME_REGISTRATION)) as reg:
            self.assertEqual(
                reg.masters,
                ["Starfield.esm", "FO4SFHome.esm", "FO4TerrainCore.esm", "FO4SFMapMarkers.esm"],
            )
            lctns = list(reg.records("LCTN"))
            self.assertEqual(len(lctns), 1)
            lcsr_raw = lctns[0].get(b"LCSR")
            self.assertEqual(len(lcsr_raw), 3 * 20)
            # Master[2] = FO4TerrainCore.esm, Master[3] = FO4SFMapMarkers.esm
            rows = [struct.unpack_from("<5I", lcsr_raw, off) for off in range(0, len(lcsr_raw), 20)]
            self.assertEqual(
                rows,
                [
                    (0x0002271F, 0x0200080A, 0x02000803, 0x00000000, 0xFFFFFFFF),
                    (0x0002271F, 0x03000800, 0x02000803, 0x0005FFFE, 0xFFFFFFFF),
                    (0x00009105, 0x03000801, 0x02000803, 0x0006FFFD, 0xFFFFFFFF),
                ],
            )

        self.assertEqual(
            make_home_planet.main(["check", "--stage", str(stage_dir), "--data", str(self.data_dir)]),
            0,
        )

        # Tampering with Data/FO4SFMapMarkers.esm after staging fails check
        mm_w2 = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM, author="tampered")
        mm_w2.write(str(mm_path), compress=False)
        self.assertEqual(
            make_home_planet.main(["check", "--stage", str(stage_dir), "--data", str(self.data_dir)]),
            1,
        )

    def test_wb_canonical_top_group_order_matches_starfield_esm_order(self) -> None:
        # Stage with all optional WB record types enabled (LTEX, WTHR, CLMT, WATR, LCTN, BIOM, ATMO, SFTR, PNDT, STDT, SUNP)
        stage_dir = self.out_root / "group-order-stage"
        self.assertEqual(
            make_home_planet.main(
                [
                    "stage",
                    "--data",
                    str(self.data_dir),
                    "--out",
                    str(stage_dir),
                    "--surface-tree",
                    "ours_empty",
                    "--sun-preset",
                    "ours",
                ]
            ),
            0,
        )
        raw_master = (stage_dir / hspec.HOME_MASTER).read_bytes()
        tes4_size = struct.unpack_from("<I", raw_master, 4)[0]
        off = 24 + tes4_size
        raw_groups: list[str] = []
        while off < len(raw_master):
            sig, gsize, label = struct.unpack_from("<4sI4s", raw_master, off)
            self.assertEqual(sig, b"GRUP")
            raw_groups.append(label.decode("ascii"))
            off += gsize

        expected_master_groups = [
            "LTEX",
            "WTHR",
            "CLMT",
            "WATR",
            "LCTN",
            "BIOM",
            "ATMO",
            "SFTR",
            "PNDT",
            "STDT",
            "SUNP",
        ]
        self.assertEqual(raw_groups, expected_master_groups)
        self.assertEqual(raw_groups, [g for g in esm.GROUP_ORDER if g in raw_groups])

        with esm.Plugin(str(stage_dir / hspec.HOME_REGISTRATION)) as reg:
            self.assertEqual(list(reg.groups.keys()), ["WRLD", "LCTN", "PNDT"])

    def test_wb1_own_weather_climate_and_atmosphere_have_zero_starfield_weather_or_sky_forms(self) -> None:
        wb1_dir = self.out_root / "wb1-variants"
        self.assertEqual(
            make_home_planet.main(["stage-wb1", "--data", str(self.data_dir), "--out", str(wb1_dir)]),
            0,
        )
        wb1_summary = json.loads((wb1_dir / "wb1_summary.json").read_text(encoding="utf-8"))
        self.assertEqual([v["variant"] for v in wb1_summary["variants"]], ["01-ours-clear-temperate", "02-starfield-control"])

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = make_home_planet.main(
                ["check", "--stage", str(wb1_dir / "01-ours-clear-temperate"), "--data", str(self.data_dir)]
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("=== BIOM & PNDT Form References ===", out)
        self.assertIn("FO4SFHome.esm:CLMT 0x01000808 (FO4SFHomeClimate)", out)
        self.assertIn("FO4SFHome.esm:WTHR 0x01000807 (FO4SFHomeClearWeather)", out)
        self.assertIn("FO4SFHome.esm:ATMO 0x01000809 (FO4SFHomeAtmosphere)", out)
        for forbidden in ("Starfield.esm:CLMT", "Starfield.esm:WTHR", "Starfield.esm:WTHS", "Starfield.esm:ATMO"):
            self.assertNotIn(forbidden, out)

        with esm.Plugin(str(wb1_dir / "01-ours-clear-temperate" / hspec.HOME_MASTER)) as hm:
            atmo_rec = next(r for r in hm.records("ATMO"))
            self.assertIsNone(atmo_rec.get(b"RFDP"))
            self.assertEqual(wb_records.inspect_beth_refl_formids(atmo_rec.get(b"REFL")), [])

    def test_wb2_own_fo4_ground_ltex_all_seven_slots_and_surface_tree_variants(self) -> None:
        wb2_dir = self.out_root / "wb2-variants"
        self.assertEqual(
            make_home_planet.main(["stage-wb2", "--data", str(self.data_dir), "--out", str(wb2_dir)]),
            0,
        )
        wb2_summary = json.loads((wb2_dir / "wb2_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(len(wb2_summary["variants"]), 4)

        v1 = wb2_dir / "01-fo4-ground-flat-nosftr"
        self.assertTrue((v1 / "Data" / "materials" / "terrain" / "FO4SFHomeGroundDirt01.mat").is_file())
        for kind in ("color", "normal", "rough"):
            self.assertTrue(
                (v1 / "Data" / "textures" / "fo4sfhome" / "landscape" / "ground" / f"fo4sfhomegrounddirt01_{kind}.dds").is_file()
            )
        with esm.Plugin(str(v1 / hspec.HOME_MASTER)) as hm:
            self.assertNotIn("FO4WG1RedRocket.esm", hm.masters)
            biom_rec = next(r for r in hm.records("BIOM"))
            pndt_rec = next(r for r in hm.records("PNDT"))
            ltex_rec = next(r for r in hm.records("LTEX"))
            self.assertEqual(ltex_rec.formid, 0x0100080A)
            lnams = [struct.unpack("<3I", d) for d in biom_rec.all(b"LNAM")]
            self.assertEqual(lnams, [(slot, 0x0100080A, 0) for slot in range(7)])
            self.assertIsNone(wb_records.pndt_surface_tree_fnam(pndt_rec))

        v2 = wb2_dir / "02-fo4-ground-flat-emptysftr"
        with esm.Plugin(str(v2 / hspec.HOME_MASTER)) as hm2:
            pndt2 = next(r for r in hm2.records("PNDT"))
            self.assertEqual(struct.unpack("<I", wb_records.pndt_surface_tree_fnam(pndt2))[0], 0x0100080B)

    def test_wb3_registration_overrides_clear_lc172_fields_without_editing_core_and_check_core_pairing(self) -> None:
        core_path = self.data_dir / "FO4TerrainCore.esm"
        core_sha_before = hashlib.sha256(core_path.read_bytes()).hexdigest()

        stage_dir = self.out_root / "wb3-installed-core"
        self.assertEqual(
            make_home_planet.main(["stage", "--data", str(self.data_dir), "--out", str(stage_dir)]),
            0,
        )
        self.assertEqual(hashlib.sha256(core_path.read_bytes()).hexdigest(), core_sha_before)
        plan = make_home_planet.load_plan(str(stage_dir))
        self.assertEqual(plan["wb3_status"], "untested")

        with esm.Plugin(str(stage_dir / hspec.HOME_REGISTRATION)) as reg:
            wrld = next(
                reg.record_at(it[1])
                for st, en in reg.groups.get("WRLD", [])
                for it in reg.walk(st, en, groups=set())
                if it[0] == "REC"
            )
            lctn = next(r for r in reg.records("LCTN"))
            self.assertEqual(esm.zstring(probe.top_level(wrld, b"FULL")), "Commonwealth")
            self.assertEqual(struct.unpack("<I", probe.top_level(wrld, b"CNAM"))[0], 0x01000808)
            self.assertEqual(struct.unpack("<I", probe.top_level(wrld, b"NAM3"))[0], 0x0100080C)
            self.assertEqual(struct.unpack("<I", probe.top_level(wrld, b"ZNAM"))[0], 0x0001BA72)
            self.assertEqual(struct.unpack("<IIhhhh", probe.top_level(wrld, b"MNAM")), (6400, 6400, -32, 31, 31, -32))
            self.assertEqual(esm.zstring(lctn.get(b"FULL")), "Commonwealth")
            self.assertEqual(lctn.get(b"DATA"), b"\x00" * 8)

        # Stage against an alternate (13-door) core directory and verify core-pairing check
        alt_core_dir = self.root / "alt_13door_core"
        alt_core_dir.mkdir(parents=True, exist_ok=True)
        alt_cw = esm.PluginWriter(["Starfield.esm"], esm.ESM, author="13door")
        with esm.Plugin(str(core_path)) as orig_cw:
            for grp in orig_cw.groups:
                for it in orig_cw.walk(*orig_cw.groups[grp][0], groups=set()):
                    if it[0] == "REC":
                        alt_cw.add(orig_cw.record_at(it[1]).copy())
        alt_cw.write(str(alt_core_dir / "FO4TerrainCore.esm"), compress=False)

        stage_13 = self.out_root / "wb3-13door-core"
        self.assertEqual(
            make_home_planet.main(
                [
                    "stage",
                    "--data",
                    str(self.data_dir),
                    "--out",
                    str(stage_13),
                    "--world-plugin-dir",
                    str(alt_core_dir),
                ]
            ),
            0,
        )
        # Check with --world-plugin-dir passes; check against mismatched Data/ core without --world-plugin-dir fails!
        self.assertEqual(
            make_home_planet.main(
                ["check", "--stage", str(stage_13), "--data", str(self.data_dir), "--world-plugin-dir", str(alt_core_dir)]
            ),
            0,
        )
        self.assertEqual(
            make_home_planet.main(["check", "--stage", str(stage_13), "--data", str(self.data_dir)]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
