"""Host-parameterised dotnet/TerrainOverlays tests (W1, R3):
- Default (no "host" key) vs explicit Mars "host" produces byte-identical (SHA-256 equal) core and Mars registration
  plugins on a synthetic master, and matches an optional live FO4TerrainCore_Mars.esm when FO4SF_STARFIELD_DATA is set.
- Custom host ("FO4SFHome.esm", custom planet_edid, surface_location, system_id, planet_id, biome, lever_keywords, and
  registration_plugin) wires WRLD overlay SNAM/PNAM, WRLD BNAM biome, LCTN PNAM + lever keywords, and a 3-master
  registration plugin overriding the custom host PNDT.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fo4sf.planet import esm, probe, records  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_pndt(formid: int, edid: str, body_name: str, system_id: int, planet_id: int, worldspaces=()) -> esm.Record:
    subs = [
        (b"EDID", esm.zbytes(edid)),
        (b"BFCB", esm.zbytes("TESFullName_Component")),
        (b"FULL", esm.zbytes(body_name)),
        (b"BFCE", b""),
    ]
    if worldspaces:
        subs.append((b"CNAM", records.pack_worldspaces(worldspaces)))
    subs += [
        (b"BDST", b""),
        (b"ANAM", esm.zbytes(body_name)),
        (b"DNAM", struct.pack("<I", 0) + b"\0"),
        (b"GNAM", struct.pack("<III", system_id, 0, planet_id)),
        (b"BDED", b""),
    ]
    return esm.Record(b"PNDT", formid, subs)


def _augment_fixture_master(base_master: Path, out_master: Path) -> None:
    """Append synthetic MarsPlanetData, SSol_PMars_Surface, and lever KYWDs to TerrainIdentityFixture's master."""
    raw = bytearray(base_master.read_bytes())
    extra_kywd = b"".join(
        esm.Record(b"KYWD", fid, [(b"EDID", esm.zbytes(edid))]).to_bytes(compress=False)
        for fid, edid in (
            (0x2CA99D, "LocTypeOverlay"),
            (0x02271F, "MapMarkerRefType"),
            (0x2C2C4F, "PCM_OverlayExclusionZone"),
            (0x1EAE24, "LocTypeNoPCMScanTreeContent"),
            (0x16B42E, "LocTypeSENotAllowed"),
        )
    )
    extra_lctn = records.new_location(
        0x01B736, "SSol_PMars_Surface", "Mars", [0x016503], 0x01A53A, 0, 4
    ).to_bytes(compress=False)
    mars_pndt = _synthetic_pndt(
        0x03F59A, "MarsPlanetData", "Mars", 0, 4, worldspaces=[(0.1, 0.2, 0x02DF8C)]
    ).to_bytes(compress=False)
    raw.extend(esm.group_bytes("KYWD", extra_kywd))
    raw.extend(esm.group_bytes("LCTN", extra_lctn))
    raw.extend(esm.group_bytes("PNDT", mars_pndt))
    out_master.parent.mkdir(parents=True, exist_ok=True)
    out_master.write_bytes(bytes(raw))


def _write_synthetic_home_master(path: Path) -> None:
    w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    own = w.own
    w.add(records.new_location(own(0x804), "SFO4SFHome_PEarth_Surface", "Earth", [0x016503], own(0x802), 0x000F04F1, 1))
    w.add(_synthetic_pndt(own(0x805), "EarthPlanetData", "Earth", 0x000F04F1, 1))
    w.add(esm.Record(b"BIOM", own(0x806), [(b"EDID", esm.zbytes("FO4SFHomeBiome")), (b"MNAM", b"\x00")]))
    w.write(str(path), compress=False)


class TerrainOverlaysHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET 9 SDK/runtime needed for TerrainOverlays writer test")
        sdks = subprocess.run([cls.dotnet, "--list-sdks"], capture_output=True, text=True, check=True)
        if not any(line.startswith("9.") for line in sdks.stdout.splitlines()):
            raise unittest.SkipTest(".NET 9 SDK/runtime needed for TerrainOverlays writer test")

        for proj in ("dotnet/TerrainIdentityFixture", "dotnet/TerrainOverlays"):
            build = subprocess.run(
                [cls.dotnet, "build", str(ROOT / proj), "-c", "Release", "--nologo"],
                capture_output=True,
                text=True,
            )
            if build.returncode:
                raise AssertionError(build.stdout + build.stderr)

        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-host-writer-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)

        raw_fixture = cls.root / "fixture_raw" / "Starfield.esm"
        fixture_dll = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        subprocess.run(
            [cls.dotnet, str(fixture_dll), str(raw_fixture), "overlay-ids", "map-marker"],
            capture_output=True,
            check=True,
        )
        cls.master = cls.root / "master" / "Starfield.esm"
        _augment_fixture_master(raw_fixture, cls.master)
        cls.writer_dll = ROOT / "dotnet/TerrainOverlays/bin/Release/net9.0/TerrainOverlays.dll"

    def _base_params(self) -> dict:
        return {
            "plugin": "SyntheticCore.esm",
            "hmin": -100.0,
            "hmax": 500.0,
            "alignment": "absolute",
            "hnam": 0,
            "overlays": [
                {
                    "world": "SyntheticWorld",
                    "block": "SyntheticBlock",
                    "location": "SyntheticLocation",
                    "tag": "Synthetic",
                    "n": 2,
                    "cell_min": 0,
                    "cell_max": 1,
                    "btd_path": "Terrain/Synthetic.btd",
                    "fnam": [0, 0, 0, 0],
                    "bounds_min_m": -200.0,
                    "bounds_max_m": 200.0,
                    "spawn": [1.0, 2.0, 3.0],
                    "spawn_cell": [0, 0],
                    "coc": "SyntheticSpawn",
                    "latitude": 0.3,
                    "longitude": -1.2,
                    "anchor": {"form_id": 0x800, "edid": "SyntheticAnchor", "local": [0.0, 0.0, 0.0]},
                }
            ],
        }

    def _run(self, name: str, params: dict, master_path: Path | None = None, setup_fn=None) -> Path:
        stage = self.root / name
        stage.mkdir(parents=True, exist_ok=True)
        if setup_fn is not None:
            setup_fn(stage)
        (stage / "overlays_params.json").write_text(json.dumps(params), encoding="utf-8")
        proc = subprocess.run(
            [self.dotnet, str(self.writer_dll), str(master_path or self.master), str(stage)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return stage

    def test_default_mars_host_is_byte_identical_to_explicit_mars_host(self) -> None:
        p_default = self._base_params()
        p_default["mars"] = {"plugin": "SyntheticCore_Mars.esm"}

        p_explicit = self._base_params()
        p_explicit["mars"] = {"plugin": "SyntheticCore_Mars.esm"}
        p_explicit["host"] = {
            "planet_plugin": "Starfield.esm",
            "planet_edid": "MarsPlanetData",
            "surface_location": "01B736:Starfield.esm",
            "system_id": 0,
            "planet_id": 4,
            "lever_keywords": [],
        }

        s_def = self._run("mars-default", p_default)
        s_exp = self._run("mars-explicit", p_explicit)

        self.assertEqual(_sha256(s_def / "SyntheticCore.esm"), _sha256(s_exp / "SyntheticCore.esm"))
        self.assertEqual(_sha256(s_def / "SyntheticCore_Mars.esm"), _sha256(s_exp / "SyntheticCore_Mars.esm"))

        with esm.Plugin(str(s_def / "SyntheticCore_Mars.esm")) as reg:
            self.assertEqual(reg.masters, ["Starfield.esm", "SyntheticCore.esm"])
            pndts = list(reg.records("PNDT", [b"PNDT"]))
            self.assertEqual(len(pndts), 1)
            self.assertEqual(pndts[0].formid, 0x03F59A)
            mws = records.master_worldspaces(pndts[0])
            self.assertEqual(len(mws), 2)
            self.assertAlmostEqual(mws[-1][0], 0.3)
            self.assertAlmostEqual(mws[-1][1], -1.2)
            self.assertEqual(mws[-1][2], 0x01000803)

    def test_custom_home_host_sets_planet_surface_biome_levers_and_registration(self) -> None:
        prm = self._base_params()
        prm["host"] = {
            "planet_plugin": "FO4SFHome.esm",
            "planet_edid": "EarthPlanetData",
            "surface_location": "000804:FO4SFHome.esm",
            "system_id": 0x000F04F1,
            "planet_id": 1,
            "biome": "000806:FO4SFHome.esm",
            "lever_keywords": ["PCM_OverlayExclusionZone", "LocTypeNoPCMScanTreeContent"],
            "registration_plugin": "SyntheticCore_Home.esm",
        }
        stage = self._run(
            "custom-home",
            prm,
            setup_fn=lambda d: _write_synthetic_home_master(d / "FO4SFHome.esm"),
        )

        with esm.Plugin(str(stage / "SyntheticCore.esm")) as core:
            self.assertEqual(core.masters, ["Starfield.esm", "FO4SFHome.esm"])
            locs = list(core.records("LCTN", [b"LCTN"]))
            self.assertEqual(len(locs), 1)
            pnam = struct.unpack("<I", locs[0].get(b"PNAM"))[0]
            self.assertEqual(pnam, 0x01000804)
            kws = records.keywords_of(locs[0])
            self.assertEqual(kws, [0x002CA99D, 0x002C2C4F, 0x001EAE24])

            wrlds = []
            for start, end in core.groups.get("WRLD", []):
                for item in core.walk(start, end, groups=set()):
                    if item[0] == "REC":
                        wrlds.append(core.record_at(item[1]))
            self.assertEqual(len(wrlds), 1)
            ov = probe.component_fields(wrlds[0], "BGSWorldSpaceOverlay_Component")
            self.assertEqual(struct.unpack("<i", ov["SNAM"])[0], 0x000F04F1)
            self.assertEqual(struct.unpack("<i", ov["PNAM"])[0], 1)
            bnam = struct.unpack("<I", probe.top_level(wrlds[0], b"BNAM"))[0]
            self.assertEqual(bnam, 0x01000806)

        with esm.Plugin(str(stage / "SyntheticCore_Home.esm")) as reg:
            self.assertEqual(reg.masters, ["Starfield.esm", "FO4SFHome.esm", "SyntheticCore.esm"])
            pndts = list(reg.records("PNDT", [b"PNDT"]))
            self.assertEqual(len(pndts), 1)
            self.assertEqual(pndts[0].formid, 0x01000805)
            mws = records.master_worldspaces(pndts[0])
            self.assertEqual(len(mws), 1)
            self.assertAlmostEqual(mws[0][0], 0.3)
            self.assertAlmostEqual(mws[0][1], -1.2)
            self.assertEqual(mws[0][2], 0x02000803)

    def test_optional_live_mars_registration_sha256_parity(self) -> None:
        live_data = os.environ.get("FO4SF_STARFIELD_DATA", "").strip()
        if not live_data:
            return
        sf_esm = Path(live_data) / "Starfield.esm"
        mars_esm = Path(live_data) / "FO4TerrainCore_Mars.esm"
        if not (sf_esm.is_file() and mars_esm.is_file()):
            return
        prm = self._base_params()
        prm["plugin"] = "FO4TerrainCore.esm"
        prm["mars"] = {"plugin": "FO4TerrainCore_Mars.esm"}
        prm["overlays"][0].update(
            {
                "world": "FO4Core_Commonwealth",
                "block": "FO4Core_CommonwealthBlock",
                "location": "FO4Core_CommonwealthLocation",
                "tag": "Commonwealth",
                "btd_path": "Terrain/FO4Core_Commonwealth.btd",
                "coc": "FO4Core_CommonwealthSpawn",
                "anchor": {"form_id": 0x800, "edid": "FO4Core_CommonwealthAnchor", "local": [0.0, 0.0, 0.0]},
            }
        )
        stage = self._run("live-mars-parity", prm, master_path=sf_esm)
        self.assertEqual(_sha256(stage / "FO4TerrainCore_Mars.esm"), _sha256(mars_esm))


if __name__ == "__main__":
    unittest.main()
