"""Offline synthetic unit tests for SanctuaryHillsWorld bounded strip extraction, BTD/objects, and zero Starfield sky refs."""
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
for sub in ("src", "scripts/prewar"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf import btd, fo4land, navmesh as nm  # noqa: E402
from fo4sf.planet import esm, home_planet_spec as hspec, records as precords, wb_records  # noqa: E402
from fo4sf.prewar import s1_spec, sanctuary_strip  # noqa: E402
import build_prewar_strip  # noqa: E402


def _synth_strip_nvnm(vx0: float, vy0: float, vz0: float) -> bytes:
    """Create a valid FO4 v15 NVNM triangle grid at FO4 world coords `(vx0, vy0, vz0)`."""
    verts = np.array(
        [[vx0, vy0, vz0], [vx0 + 700.0, vy0, vz0], [vx0 + 700.0, vy0 + 700.0, vz0], [vx0, vy0 + 700.0, vz0]],
        dtype="<f4",
    )
    tris = np.zeros(2, nm.TRI_DTYPE)
    tris[0] = ((0, 1, 2), (-1, -1, 1), np.float32(nm.FLT_MAX), 0, nm.F_FOUND, 0)
    tris[1] = ((0, 2, 3), (0, -1, -1), np.float32(nm.FLT_MAX), 0, nm.F_FOUND, 0)
    return b"".join([
        struct.pack("<IIIhh", 15, nm.MAGIC, 0, -21, 21),
        struct.pack("<I", len(verts)) + verts.tobytes(),
        struct.pack("<I", len(tris)) + tris.tobytes(),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I8f", 1, 1.0, 1.0, *verts.min(0), *verts.max(0)),
        struct.pack("<I2h", 2, 0, 1),
    ])


def _rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0) -> bytes:
    body = b"".join(s + struct.pack("<H", len(d)) + d for s, d in subs)
    return struct.pack("<4sIIIIHH", sig, len(body), flags, fid, 0, 131, 0) + body


def _grup(label: bytes, gtype: int, payload: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload


def _encode_vhgt_flat(base_step: float, grid_steps: np.ndarray) -> bytes:
    """Encode a `(33, 33)` grid in VHGT 8 ft height steps into Fallout 4 `VHGT` bytes."""
    buf = bytearray()
    buf += struct.pack("<f", float(base_step))
    row_ref = 0
    for y in range(fo4land.GRID):
        prev = row_ref
        for x in range(fo4land.GRID):
            cur = int(round(grid_steps[y, x] - base_step))
            delta = cur - prev
            buf.append(delta & 0xFF)
            prev = cur
            if x == 0:
                row_ref = cur
    buf += b"\x00\x00\x00"
    return bytes(buf)


def _write_synthetic_fo4_sanctuary(out_path: Path) -> None:
    """Create a tiny synthetic Fallout4 ESM containing a Sanctuary strip WRLD, LAND, NAVM, STAT, and REFRs."""
    tes4 = _rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 20, 0x010000))])
    stat_fid = 0x00030001
    door_fid = 0x00030002
    stat_rec = _rec(b"STAT", stat_fid, [(b"EDID", b"PrewarHouse01\x00"), (b"MODL", b"Architecture\\Sanctuary\\PrewarHouse01.nif\x00")])
    door_rec = _rec(b"DOOR", door_fid, [(b"EDID", b"Res01ModernDoor01In\x00"), (b"MODL", b"Architecture\\Buildings\\Residential\\Res01ModernDoor01In.nif\x00")])
    stat_grup = _grup(b"STAT", 0, stat_rec) + _grup(b"DOOR", 0, door_rec)

    wrld_rec = _rec(b"WRLD", s1_spec.SANCTUARY_WRLD_FID, [(b"EDID", b"SanctuaryHillsWorld\x00")])
    pers_cell = _rec(b"CELL", 0x000A8000, [(b"EDID", b"SanctuaryPersist\x00")])
    px_u, py_u, pz_u = [v * 70.0 for v in s1_spec.SANCTUARY_KEY_COORDS_M["player_house_door"]]
    pers_refr = _rec(
        b"REFR",
        0x000A8001,
        [
            (b"EDID", b"HouseDoorRef\x00"),
            (b"NAME", struct.pack("<I", door_fid)),
            (b"ONAM", b""),
            (b"DATA", struct.pack("<6f", px_u, py_u, pz_u, 0.0, 0.0, 0.5)),
        ],
    )
    pers_grup = _grup(struct.pack("<I", 0x000A8000), 6, _grup(struct.pack("<I", 0x000A8000), 8, pers_refr))

    # Build 4 corners + center LAND cells in (-23..-19, 19..23)
    steps = np.zeros((fo4land.GRID, fo4land.GRID), dtype=np.float64)
    for y in range(fo4land.GRID):
        steps[y, :] = np.arange(fo4land.GRID) * 0.25
    vhgt = _encode_vhgt_flat(7700.0 / 8.0, steps)  # ~7700 FO4 units (~110m)

    cell_chunks = []
    next_fid = 0x000A8100
    tile = sanctuary_strip.strip_sf_tile()
    ox, oy = tile.origin_m
    for idx, (gx, gy) in enumerate([(-23, 19), (-21, 21), (-19, 23)]):
        cfid = next_fid + idx * 4
        crec = _rec(b"CELL", cfid, [(b"XCLC", struct.pack("<iii", gx, gy, 0))])
        lrec = _rec(b"LAND", cfid + 1, [(b"VHGT", vhgt)])
        nvnm = _rec(b"NAVM", cfid + 2, [(b"NVNM", _synth_strip_nvnm((ox + 10.0 * idx) * 70.0, oy * 70.0, 7700.0))])
        rx = (gx + 0.5) * 4096.0
        ry = (gy + 0.5) * 4096.0
        rrec = _rec(
            b"REFR",
            cfid + 3,
            [
                (b"NAME", struct.pack("<I", stat_fid)),
                (b"DATA", struct.pack("<6f", rx, ry, 7700.0, 0.0, 0.0, 0.0)),
            ],
        )
        t_grp = _grup(struct.pack("<I", cfid), 9, lrec + nvnm + rrec)
        c_grp = _grup(struct.pack("<I", cfid), 6, t_grp)
        cell_chunks.append(crec + c_grp)

    sub_grp = _grup(struct.pack("<hh", 21, -21), 5, b"".join(cell_chunks))
    blk_grp = _grup(struct.pack("<hh", 0, -1), 4, sub_grp)
    wrld_children = _grup(struct.pack("<I", s1_spec.SANCTUARY_WRLD_FID), 1, pers_cell + pers_grup + blk_grp)
    wrld_top = _grup(b"WRLD", 0, wrld_rec + wrld_children)

    out_path.write_bytes(tes4 + stat_grup + wrld_top)


class SanctuaryStripTests(unittest.TestCase):
    def test_strip_sf_tile_covers_all_sanctuary_coords(self) -> None:
        tile = sanctuary_strip.strip_sf_tile()
        self.assertEqual(tile.n, 4)
        self.assertEqual((tile.cx0, tile.cy0), (-14, 11))
        lo_local = -(tile.n // 2) * 100.0
        hi_local = (tile.n - tile.n // 2) * 100.0
        for name, (px, py, _pz) in s1_spec.SANCTUARY_KEY_COORDS_M.items():
            self.assertTrue(tile.contains(px, py), f"{name} ({px}, {py}) outside tile CW bounds {tile.bounds_m}")
            lx, ly = tile.to_local(px, py)
            self.assertGreaterEqual(lx, lo_local, f"{name} clipped left")
            self.assertLess(lx, hi_local, f"{name} clipped right")
            self.assertGreaterEqual(ly, lo_local, f"{name} clipped bottom")
            self.assertLess(ly, hi_local, f"{name} clipped top")

    def test_synthetic_strip_btd_objects_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fo4_path = root / "Fallout4_Synth.esm"
            _write_synthetic_fo4_sanctuary(fo4_path)

            out_dir = root / "stage"
            rep_path = root / "report.json"
            rc = build_prewar_strip.main([
                "--fo4-esm", str(fo4_path),
                "--out-dir", str(out_dir),
                "--emit-sky-esm",
                "--report-json", str(rep_path),
            ])
            self.assertEqual(rc, 0)
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
            self.assertEqual(rep["fo4_cells"], 3)
            self.assertEqual(rep["fo4_lands"], 3)
            self.assertEqual(rep["sf_tile_n"], 4)
            self.assertGreaterEqual(rep["placed_objects"], 4)

            objs = json.loads((out_dir / "objects.json").read_text(encoding="utf-8"))
            self.assertTrue(all(isinstance(r["base"], int) and 0 <= r["base"] < len(objs["bases"]) for r in objs["refs"]))

            btd_path = out_dir / "Data" / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd"
            parsed = btd.read(btd_path.read_bytes())
            self.assertEqual(parsed.heights_raw.shape, (512, 512))
            meters = parsed.heights_m()
            self.assertGreater(float(np.min(meters)), 95.0)
            self.assertLess(float(np.max(meters)), 125.0)

            prm = json.loads((out_dir / "overlays_params.json").read_text(encoding="utf-8"))
            self.assertEqual(prm["host"]["planet_plugin"], hspec.HOME_MASTER)
            self.assertEqual(prm["host"]["surface_location"], f"{hspec.SURFACE_LOC:06X}:{hspec.HOME_MASTER}")
            self.assertEqual(prm["host"]["biome"], f"{hspec.BIOME:06X}:{hspec.HOME_MASTER}")
            self.assertEqual(prm["host"]["registration_plugin"], "FO4SFPrewar_Sanctuary_Home.esm")
            self.assertIn("latitude", prm["overlays"][0])
            self.assertIn("longitude", prm["overlays"][0])

            sky_path = out_dir / "FO4SFPrewarSky.esm"
            sanctuary_strip.verify_zero_starfield_sky_refs(str(sky_path))

    def test_verify_zero_starfield_sky_refs_rejects_foreign_or_pndt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # 1. Non-zero WTHR external imageSpace link
            bad_wthr = root / "BadWthr.esm"
            w = esm.PluginWriter([], esm.ESM)
            w.add(wb_records.build_home_weather(wb_records.HOME_WEATHER))
            w.add(wb_records.build_home_climate(wb_records.HOME_CLIMATE, weather_formid=wb_records.HOME_WEATHER))
            w.add(wb_records.build_home_atmosphere(wb_records.HOME_ATMO))
            # Mutate LNAM on WTHR cleanly to non-zero foreign Starfield ref
            w.records[0].subs = [
                (sig, struct.pack("<I", 0x00012345) if sig == b"LNAM" else data)
                for sig, data in w.records[0].subs
            ]
            w.write(str(bad_wthr), compress=False)
            with self.assertRaises(ValueError):
                sanctuary_strip.verify_zero_starfield_sky_refs(str(bad_wthr))

            # 2. Unexpected PNDT record present
            bad_pndt = root / "BadPndt.esm"
            w2 = esm.PluginWriter([], esm.ESM)
            w2.add(wb_records.build_home_weather(wb_records.HOME_WEATHER))
            w2.add(esm.Record(b"PNDT", 0x000805, [(b"EDID", esm.zbytes("IllegalPndt"))]))
            w2.write(str(bad_pndt), compress=False)
            with self.assertRaises(ValueError):
                sanctuary_strip.verify_zero_starfield_sky_refs(str(bad_pndt))

    def test_bind_prewar_world_to_home_replaces_starfield_water_and_climate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world_p = root / "FO4SFPrewar_Sanctuary.esm"
            w = esm.PluginWriter(["Starfield.esm", hspec.HOME_MASTER], esm.ESM)
            w.add(esm.Record(b"LCTN", w.own(0x802), [(b"EDID", esm.zbytes("FO4SF_PrewarSanctuaryWorldLocation")), (b"PNAM", struct.pack("<I", 0x01000804))]))
            w.add(
                esm.Record(
                    b"WRLD",
                    w.own(0x803),
                    [
                        (b"EDID", esm.zbytes("FO4SF_PrewarSanctuaryWorld")),
                        (b"FULL", esm.zbytes("Sanctuary Hills")),
                        (b"BNAM", struct.pack("<I", 0x002A3777)),  # stale Starfield biome
                        (b"BNAM", struct.pack("<I", 0x01000806)),  # FO4SFHome biome
                        (b"NAM3", struct.pack("<I", 0x00000018)),  # Starfield WaterClear
                    ],
                )
            )
            w.write(str(world_p), compress=False)
            with self.assertRaises(ValueError):
                sanctuary_strip.verify_zero_starfield_sky_refs(str(world_p))

            rep = sanctuary_strip.bind_prewar_world_to_home(str(world_p))
            self.assertIsNotNone(rep["prewar_weather_fid"])
            self.assertNotEqual(rep["prewar_climate_fid"], "0x01000808")  # S1-11: distinct pre-war climate/weather
            self.assertEqual(rep["home_water_fid"], "0x0100080C")
            sanctuary_strip.verify_zero_starfield_sky_refs(str(world_p))
            with esm.Plugin(str(world_p)) as wp:
                self.assertEqual([w.edid for w in wp.records("WTHR", [b"WTHR"])], ["FO4SF_PrewarClearWeather"])
                self.assertEqual([c.edid for c in wp.records("CLMT", [b"CLMT"])], ["FO4SF_PrewarSanctuaryClimate"])

    def test_navmesh_door_rig_and_combined_pndt_coordination(self) -> None:
        """S1-04 navmesh export, S1-14 door hinge/ONAM rigging, and S1-07 combined PNDT 0x805 validation."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fo4_path = root / "Fallout4_Synth.esm"
            _write_synthetic_fo4_sanctuary(fo4_path)
            door_manifest_p = root / "doors.json"
            door_manifest_p.write_text(
                json.dumps({
                    "meshes/architecture/buildings/residential/res01moderndoor01in.nif": {
                        "origin_offset": [0.5, 0.0, 0.0],
                        "anim_graph": "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx",
                        "bounds": [[-0.5, -0.1, -1.0], [0.5, 0.1, 1.0]],
                    }
                }),
                encoding="utf-8",
            )
            out_dir = root / "stage"
            rep_p = root / "report.json"
            rc = build_prewar_strip.main([
                "--fo4-esm", str(fo4_path),
                "--out-dir", str(out_dir),
                "--door-manifest", str(door_manifest_p),
                "--report-json", str(rep_p),
            ])
            self.assertEqual(rc, 0)
            rep = json.loads(rep_p.read_text(encoding="utf-8"))
            self.assertEqual(rep["sf_navms"], 3)
            prm = json.loads((out_dir / "overlays_params.json").read_text(encoding="utf-8"))
            self.assertEqual(prm["navmesh"], "navmesh.json")
            ndoc = json.loads((out_dir / "navmesh.json").read_text(encoding="utf-8"))
            self.assertEqual(ndoc["world"], "FO4SF_PrewarSanctuaryWorld")
            self.assertEqual(len(ndoc["navmeshes"]), 3)

            objs = json.loads((out_dir / "objects.json").read_text(encoding="utf-8"))
            door_base = next(b for b in objs["bases"] if b["edid"] == "FO4Prewar_Res01ModernDoor01In")
            self.assertIn("door", door_base)
            door_ref = next(r for r in objs["refs"] if r["src"] == "0A8001:Fallout4.esm")
            self.assertTrue(door_ref.get("open_by_default"))
            # Hinge origin_offset [0.5, 0, 0] rotated by rotZ=0.5 shifts x, y away from unshifted FO4 coord
            tx, ty, _ = s1_spec.SANCTUARY_KEY_COORDS_M["player_house_door"]
            tile = sanctuary_strip.strip_sf_tile()
            lx, ly = tile.to_local(tx, ty)
            self.assertGreater(abs(door_ref["pos"][0] - lx), 0.2)

            # S1-07: combined PNDT 0x805 passes check_load_order_overrides when preserving Commonwealth
            home_p = root / hspec.HOME_MASTER
            pw_home = esm.PluginWriter(["Starfield.esm"], esm.ESM)
            # Minimal valid PNDT with BDST..BDED + ANAM + GNAM
            pndt_subs = [
                (b"EDID", esm.zbytes("FO4SF_EarthPlanetData")),
                (b"BDST", b""),
                (b"ANAM", esm.zbytes(hspec.DEFAULT_BODY_NAME)),
                (b"GNAM", struct.pack("<III", hspec.DEFAULT_HOME_SYSTEM_ID, 0, hspec.DEFAULT_HOME_PLANET_ID)),
                (b"BDED", b""),
            ]
            pw_home.add(esm.Record(b"PNDT", pw_home.own(hspec.PLANET), pndt_subs))
            pw_home.write(str(home_p), compress=False)

            core_p = root / hspec.CORE_PLUGIN
            pw_c = esm.PluginWriter(["Starfield.esm"], esm.ESM)
            pw_c.add(esm.Record(b"WRLD", pw_c.own(hspec.CORE_WRLD_LOCAL), [(b"EDID", esm.zbytes("FO4Core_Commonwealth"))]))
            pw_c.write(str(core_p), compress=False)

            sanc_p = root / s1_spec.PLUGIN_PREWAR_WORLD
            pw_s = esm.PluginWriter(["Starfield.esm", hspec.HOME_MASTER], esm.ESM)
            pw_s.add(esm.Record(b"WRLD", pw_s.own(0x803), [(b"EDID", esm.zbytes("FO4SF_PrewarSanctuaryWorld"))]))
            pw_s.write(str(sanc_p), compress=False)

            core_home_p = root / hspec.HOME_REGISTRATION
            pw_ch = esm.PluginWriter(["Starfield.esm", hspec.HOME_MASTER, hspec.CORE_PLUGIN], esm.ESM)
            with esm.Plugin(str(home_p)) as hm:
                h_rec = list(hm.records("PNDT", [b"PNDT"]))[0]
            pw_ch.add(precords.registration_record(h_rec, (1 << 24) | hspec.PLANET, [(-1.2, 0.3, (2 << 24) | hspec.CORE_WRLD_LOCAL)]))
            pw_ch.write(str(core_home_p), compress=False)

            sanc_reg_p = root / hspec.PREWAR_HOME_REGISTRATION
            rep_comb = sanctuary_strip.coordinate_home_pndt_plugin(
                str(home_p), str(sanc_p), str(sanc_reg_p), terrain_core_home_path=str(core_home_p)
            )
            self.assertTrue(rep_comb["combined_with_core_home"])
            self.assertEqual(len(rep_comb["worlds"]), 2)
            probs = hspec.check_load_order_overrides(
                [str(core_p), str(home_p), str(core_home_p), str(sanc_p), str(sanc_reg_p)],
                allow_prewar_home_pair=True,
            )
            self.assertEqual(probs, [])

            # Clobbering registration (Sanctuary only) MUST still be refused when FO4TerrainCore_Home is active
            sanc_solo_p = root / hspec.PREWAR_HOME_REGISTRATION
            sanctuary_strip.coordinate_home_pndt_plugin(str(home_p), str(sanc_p), str(sanc_solo_p), terrain_core_home_path=None)
            probs_bad = hspec.check_load_order_overrides(
                [str(core_p), str(home_p), str(core_home_p), str(sanc_p), str(sanc_solo_p)],
                allow_prewar_home_pair=True,
            )
            self.assertTrue(any("missing 1 world" in pr or "duplicate PNDT" in pr for pr in probs_bad), probs_bad)


if __name__ == "__main__":
    unittest.main()
