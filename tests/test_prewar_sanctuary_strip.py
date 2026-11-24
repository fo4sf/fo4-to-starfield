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

from fo4sf import btd, fo4land  # noqa: E402
from fo4sf.planet import esm, home_planet_spec as hspec, wb_records  # noqa: E402
from fo4sf.prewar import s1_spec, sanctuary_strip  # noqa: E402
import build_prewar_strip  # noqa: E402


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
    stat_rec = _rec(b"STAT", stat_fid, [(b"EDID", b"PrewarHouse01\x00"), (b"MODL", b"Architecture\\Sanctuary\\PrewarHouse01.nif\x00")])
    stat_grup = _grup(b"STAT", 0, stat_rec)

    wrld_rec = _rec(b"WRLD", s1_spec.SANCTUARY_WRLD_FID, [(b"EDID", b"SanctuaryHillsWorld\x00")])
    pers_cell = _rec(b"CELL", 0x000A8000, [(b"EDID", b"SanctuaryPersist\x00")])
    px_u, py_u, pz_u = [v * 70.0 for v in s1_spec.SANCTUARY_KEY_COORDS_M["player_house_door"]]
    pers_refr = _rec(
        b"REFR",
        0x000A8001,
        [
            (b"EDID", b"HouseDoorRef\x00"),
            (b"NAME", struct.pack("<I", stat_fid)),
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
    for idx, (gx, gy) in enumerate([(-23, 19), (-21, 21), (-19, 23)]):
        cfid = next_fid + idx * 4
        crec = _rec(b"CELL", cfid, [(b"XCLC", struct.pack("<iii", gx, gy, 0))])
        lrec = _rec(b"LAND", cfid + 1, [(b"VHGT", vhgt)])
        nvnm = _rec(b"NAVM", cfid + 2, [(b"NVNM", b"\x00" * 16)])
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
                "--report-json", str(rep_path),
            ])
            self.assertEqual(rc, 0)
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
            self.assertEqual(rep["fo4_cells"], 3)
            self.assertEqual(rep["fo4_lands"], 3)
            self.assertEqual(rep["sf_tile_n"], 4)
            self.assertGreaterEqual(rep["placed_objects"], 4)

            btd_path = out_dir / "Data" / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd"
            parsed = btd.read(btd_path.read_bytes())
            self.assertEqual(parsed.heights_raw.shape, (512, 512))
            meters = parsed.heights_m()
            self.assertGreater(float(np.min(meters)), 95.0)
            self.assertLess(float(np.max(meters)), 125.0)

            prm = json.loads((out_dir / "overlays_params.json").read_text(encoding="utf-8"))
            self.assertEqual(prm["host"]["planet_plugin"], hspec.HOME_MASTER)
            self.assertIn(f"0x{0x01000000 | hspec.SURFACE_LOC:08X}", prm["host"]["surface_location"])
            self.assertIn(f"0x{0x01000000 | hspec.BIOME:08X}", prm["host"]["biome"])

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


if __name__ == "__main__":
    unittest.main()
