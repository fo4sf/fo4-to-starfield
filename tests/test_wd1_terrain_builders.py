"""Synthetic unit tests for `WD1` parameterized terrain builders:
  - `src/fo4sf/fo4land.py` (`read_world_load_order`, `world_grid_meta`)
  - `scripts/terrain/make_cw_overlays.py` (`--fo4-world`, `--fo4-masters`, `--water-height-m`, R4 path guard)
  - `dotnet/Fo4Land` (`--master <esm>` repeatable for LAND, `export-exterior`, `export-mapmarkers`, `export-furniture`)
  - `scripts/terrain/make_core64c.py` (`--world-key` reading `src/fo4sf/core/world_registry.py`, R4 path guard)

Zero game files are read; every `.esm` and `.btd` byte is generated synthetically in temporary directories.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts" / "terrain") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "terrain"))

from fo4sf import ba2, btd, fo4land  # noqa: E402
from fo4sf.terrain.path_guard import OutputPathRefusedError, refuse_unsafe_output_path  # noqa: E402
import make_cw_overlays as mco  # noqa: E402

# Authentic cd03411a SHA-256 pins on the synthetic 4x4 Commonwealth LAND + BA2 fixture (R12 / C8)
CD03411A_DEFAULT_CW_BTD_SHA256 = "979ce44f03f32ffe12da7426d2ecfbe7c16b1a37d44754c717a0fc1f9a3efbf5"
CD03411A_DEFAULT_CW_MASK_SHA256 = "8daa820a2aefcf6ff9810f471cc25fa587fccfc08ab071cb3e7bd5451a4d0fd7"
CD03411A_DEFAULT_CW_PARAMS_SHA256 = "10c435cde40dfbfab3f3ddb61cd852490b27314d3a34a847c29a588110b36eea"
CD03411A_DEFAULT_CW_PLAN_SHA256 = "bf15639d058d4d8d234c971c29308e5aa657731502d3ef5e9a7d52e6a70c049c"

_spec_mc = importlib.util.spec_from_file_location("make_core64c_wd1", ROOT / "scripts" / "terrain" / "make_core64c.py")
mc64 = importlib.util.module_from_spec(_spec_mc)
assert _spec_mc and _spec_mc.loader
_spec_mc.loader.exec_module(mc64)


def _sub(sig: bytes, data: bytes) -> bytes:
    return sig + struct.pack("<H", len(data)) + data


def _rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0) -> bytes:
    payload = b"".join(_sub(s, d) for s, d in subs)
    return struct.pack("<4sIIIIHH", sig, len(payload), flags, fid, 0, 131, 0) + payload


def _grup(label: bytes | int, items: list[bytes], gtype: int = 0) -> bytes:
    if isinstance(label, int):
        label = struct.pack("<I", label)
    body = b"".join(items)
    return struct.pack("<4sI4siHHHH", b"GRUP", 24 + len(body), label, gtype, 0, 0, 0, 0) + body


def _z(text: str) -> bytes:
    return text.encode("cp1252") + b"\0"


def _write_synthetic_sf_terrain_ba2(sf_data_dir: str) -> None:
    """Create minimal synthetic `Starfield - Terrain01.ba2` containing `terrain/tempjemisonworld.btd`."""
    os.makedirs(sf_data_dir, exist_ok=True)
    plain = 0x001235C2
    table = [plain]
    quad = np.zeros((2, 2, 8), dtype=np.uint8)
    quad[:, :, 0] = 1  # nlt - 1 = 0 -> table[0] = LDirtFootprints01
    raw_h = np.zeros((128, 128), dtype=np.uint16)
    raw_w = np.zeros((128, 128), dtype=np.uint16)
    btd_bytes = btd.write(btd.Btd(6, -100.0, 100.0, table, raw_h, raw_w, quad))

    # Build uncompressed GNRL BA2 v1 header + 1 entry
    name_bytes = b"terrain/tempjemisonworld.btd"
    header = struct.pack("<4sI4sIQ", b"BTDX", 1, b"GNRL", 1, 24 + 36 + len(btd_bytes))
    data_off = 24 + 36
    entry = struct.pack(
        "<I4sBBHIIIQI",
        0x12345678,
        b"btd\0",
        0,
        0,
        0,
        0,
        data_off,
        0,  # packed=0 -> uncompressed
        len(btd_bytes),
        0xBAADF00D,
    )[:36]
    # Re-pack exact 36-byte GNRL entry: hash(4), ext(4), dirHash(4), flags(4), offset(8), packed(4), unpacked(4), align(4)
    entry = struct.pack(
        "<I4sIIQIII",
        0x12345678,
        b"btd\0",
        0x87654321,
        0x00100100,
        data_off,
        0,
        len(btd_bytes),
        0xBAADF00D,
    )
    name_table = struct.pack("<H", len(name_bytes)) + name_bytes
    ba2_bytes = header + entry + btd_bytes + name_table
    # Fix name_table offset at bytes 16..24
    ba2_bytes = (
        ba2_bytes[:16]
        + struct.pack("<Q", 24 + 36 + len(btd_bytes))
        + ba2_bytes[24:]
    )
    for idx in range(1, 5):
        p = os.path.join(sf_data_dir, f"Starfield - Terrain0{idx}.ba2")
        if idx == 1:
            Path(p).write_bytes(ba2_bytes)
    # Verify our synthetic BA2 reads back cleanly
    chk = ba2.Ba2(os.path.join(sf_data_dir, "Starfield - Terrain01.ba2"))
    assert chk.find("terrain/tempjemisonworld.btd") is not None


def _build_master_and_dlc_plugins(master_path: str, dlc_path: str) -> None:
    """Write synthetic `Fallout4.esm` (defines `STAT` base `0x000810` + `Commonwealth` `0x00003C`) and
    `DLCCoast.esm` (masters `Fallout4.esm`, defines `DLC03FarHarbor` `0x01000B0F` placing `0x000810` and
    overrides `Commonwealth` cell `(0, 0)`)."""
    steps_cw = np.zeros((33, 33), dtype=np.int64) + 10
    vhgt_cw = fo4land.encode_vhgt(0.0, steps_cw)

    tes4_master = _rec(b"TES4", 0, [(_sub_pair := (b"HEDR", struct.pack("<fiI", 1.0, 8, 0x900)))], flags=0x1)
    stat_dock = _rec(
        b"STAT",
        0x000810,
        [(b"EDID", _z("SynthCoastDock01")), (b"MODL", _z("Architecture\\Dock\\SynthDock01.nif"))],
    )
    furn_chair = _rec(
        b"FURN",
        0x000811,
        [(b"EDID", _z("SynthBaseChair01")), (b"MODL", _z("Furniture\\SynthChair01.nif"))],
    )
    ref_cw_keep = _rec(
        b"REFR",
        0x000820,
        [(b"NAME", struct.pack("<I", 0x000810)), (b"DATA", struct.pack("<6f", 256.0, 256.0, 80.0, 0.0, 0.0, 0.0))],
    )
    ref_cw_del = _rec(
        b"REFR",
        0x000821,
        [(b"NAME", struct.pack("<I", 0x000810)), (b"DATA", struct.pack("<6f", 512.0, 512.0, 80.0, 0.0, 0.0, 0.0))],
    )
    cw_sub_items: list[bytes] = []
    cw_next = 0x000900
    for cx in range(-6, 6):
        for cy in range(-6, 6):
            if (cx, cy) == (0, 0):
                cfid = 0x000830
            else:
                cfid = cw_next
                cw_next += 1
            lfid = cw_next
            cw_next += 1
            kids = [_rec(b"LAND", lfid, [(b"DATA", b"\0\0\0\0"), (b"VHGT", vhgt_cw)])]
            if (cx, cy) == (0, 0):
                kids.extend([ref_cw_keep, ref_cw_del])
            cw_sub_items.append(_rec(b"CELL", cfid, [(b"XCLC", struct.pack("<iiI", cx, cy, 0))]))
            cw_sub_items.append(_grup(cfid, [_grup(cfid, kids, 9)], 6))
    cw_wrld = [
        _rec(b"WRLD", 0x00003C, [(b"EDID", _z("Commonwealth")), (b"DNAM", struct.pack("<2f", -2048.0, 0.0))]),
        _grup(
            0x00003C,
            [
                _grup(
                    struct.pack("<hh", 0, 0),
                    [_grup(struct.pack("<hh", 0, 0), cw_sub_items, 5)],
                    4,
                )
            ],
            1,
        ),
    ]
    Path(master_path).write_bytes(
        tes4_master
        + _grup(b"STAT", [stat_dock])
        + _grup(b"FURN", [furn_chair])
        + _grup(b"WRLD", cw_wrld)
    )

    # DLC plugin: master index 0 = Fallout4.esm, own index 1 = DLCCoast.esm
    tes4_dlc = _rec(
        b"TES4",
        0,
        [
            (b"HEDR", struct.pack("<fiI", 1.0, 16, 0x950)),
            (b"MAST", _z(os.path.basename(master_path))),
            (b"DATA", struct.pack("<Q", 0)),
        ],
        flags=0x1,
    )
    dlc_furn = _rec(
        b"FURN",
        0x01000850,
        [(b"EDID", _z("SynthDlcBench01")), (b"MODL", _z("DLC03\\Furniture\\SynthBench01.nif"))],
    )

    # Override Commonwealth (0x00003C) cell (0,0): delete 0x000821, move 0x000820, add 0x01000860
    ref_cw_moved = _rec(
        b"REFR",
        0x000820,
        [(b"NAME", struct.pack("<I", 0x000810)), (b"DATA", struct.pack("<6f", 300.0, 300.0, 96.0, 0.0, 0.0, 0.0))],
    )
    ref_cw_deleted = _rec(b"REFR", 0x000821, [], flags=0x20)
    ref_cw_added = _rec(
        b"REFR",
        0x01000860,
        [(b"NAME", struct.pack("<I", 0x000810)), (b"DATA", struct.pack("<6f", 600.0, 600.0, 80.0, 0.0, 0.0, 0.0))],
    )
    cw_cell_ovr = _rec(b"CELL", 0x000830, [(b"XCLC", struct.pack("<iiI", 0, 0, 0))])
    cw_ovr_wrld = [
        _rec(b"WRLD", 0x00003C, [(b"EDID", _z("Commonwealth")), (b"DNAM", struct.pack("<2f", -2048.0, 0.0))]),
        _grup(
            0x00003C,
            [
                _grup(
                    struct.pack("<hh", 0, 0),
                    [_grup(struct.pack("<hh", 0, 0), [cw_cell_ovr, _grup(0x000830, [_grup(0x000830, [ref_cw_moved, ref_cw_deleted, ref_cw_added], 9)], 6)], 5)],
                    4,
                )
            ],
            1,
        ),
    ]

    # DLC03FarHarbor (0x01000B0F): cells x=-3..2, y=-3..2; island cells (-2..1, -2..1) have VHGT=120 units (flat plateau
    # tapering to 0 on outer ring), sea border cells have no LAND (default_land = 0.0, water = 450.0 units = 6.4286 m).
    fh_sub_items: list[bytes] = []
    next_fid = 0x01000C00
    for cx in range(-4, 4):
        for cy in range(-4, 4):
            cfid = next_fid
            next_fid += 1
            fh_sub_items.append(_rec(b"CELL", cfid, [(b"XCLC", struct.pack("<iiI", cx, cy, 0))]))
            children: list[bytes] = []
            if -2 <= cx <= 1 and -2 <= cy <= 1:
                lfid = next_fid
                next_fid += 1
                # Smooth island dome whose outer edge is 0 so sea cells join at 0.0 units with zero step
                gx = (cx + np.arange(33) / 32.0 + 2.0) / 4.0  # 0..1 across x=-2..2
                gy = (cy + np.arange(33) / 32.0 + 2.0) / 4.0  # 0..1 across y=-2..2
                xx, yy = np.meshgrid(gx, gy)
                dome = np.sin(np.pi * np.clip(xx, 0.0, 1.0)) * np.sin(np.pi * np.clip(yy, 0.0, 1.0))
                steps = np.round(dome * 120.0).astype(np.int64)  # max 960 units = 13.71 m (> 6.43 m sea)
                vhgt = fo4land.encode_vhgt(0.0, steps)
                children.append(_rec(b"LAND", lfid, [(b"DATA", b"\0\0\0\0"), (b"VHGT", vhgt)]))
            if (cx, cy) == (0, 0):
                # Reference in DLC03FarHarbor pointing to Fallout4.esm base 0x000810!
                rfid = 0x01000890
                children.append(
                    _rec(
                        b"REFR",
                        rfid,
                        [
                            (b"NAME", struct.pack("<I", 0x000810)),
                            (b"DATA", struct.pack("<6f", 512.0, 512.0, 960.0, 0.0, 0.0, 0.0)),
                        ],
                    )
                )
            fh_sub_items.append(_grup(cfid, [_grup(cfid, children, 9)], 6))

    # Persistent map marker in DLC03FarHarbor top cell
    fh_top_fid = 0x01000B10
    fh_marker = _rec(
        b"REFR",
        0x01000895,
        [
            (b"EDID", _z("SynthFarHarborDockMarker")),
            (b"NAME", struct.pack("<I", 0x000010)),
            (b"XMRK", b""),
            (b"FNAM", b"\x03"),
            (b"FULL", _z("SynthHarbor")),
            (b"TNAM", bytes([5, 0])),
            (b"DATA", struct.pack("<6f", 256.0, 256.0, 960.0, 0.0, 0.0, 0.0)),
        ],
        flags=0x400,
    )
    fh_wrld = [
        _rec(b"WRLD", 0x01000B0F, [(b"EDID", _z("DLC03FarHarbor")), (b"DNAM", struct.pack("<2f", 0.0, 450.0))]),
        _grup(
            0x01000B0F,
            [
                _rec(b"CELL", fh_top_fid, [], flags=0x400),
                _grup(fh_top_fid, [_grup(fh_top_fid, [fh_marker], 8)], 6),
                _grup(struct.pack("<hh", 0, 0), [_grup(struct.pack("<hh", 0, 0), fh_sub_items, 5)], 4),
            ],
            1,
        ),
    ]

    Path(dlc_path).write_bytes(
        tes4_dlc
        + _grup(b"FURN", [dlc_furn])
        + _grup(b"WRLD", cw_ovr_wrld + fh_wrld)
    )


class Wd1TerrainBuildersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dotnet = shutil.which("dotnet")
        if cls.dotnet:
            build = subprocess.run(
                [cls.dotnet, "build", str(ROOT / "dotnet" / "Fo4Land"), "-c", "Release", "--nologo"],
                capture_output=True,
                text=True,
            )
            if build.returncode:
                raise AssertionError(build.stdout + build.stderr)
            cls.fo4land_dll = ROOT / "dotnet" / "Fo4Land" / "bin" / "Release" / "net9.0" / "Fo4Land.dll"
        else:
            cls.fo4land_dll = None

    def test_fo4land_load_order_resolves_dlc_world_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            master = os.path.join(tmp, "Fallout4.esm")
            dlc = os.path.join(tmp, "DLCCoast.esm")
            _build_master_and_dlc_plugins(master, dlc)

            meta = fo4land.world_grid_meta([master, dlc], "DLC03FarHarbor")
            self.assertEqual(meta["cell_bbox"], (-4, 3, -4, 3))
            self.assertEqual(meta["land_bbox"], (-2, 1, -2, 1))
            self.assertEqual(meta["dnam"], (0.0, 450.0))

            fh = fo4land.read_world_load_order([master, dlc], "DLC03FarHarbor", refs=True)
            self.assertEqual(len(fh["cells"]), 64)
            self.assertIsNotNone(fh["cells"][(0, 0)]["vhgt"])
            self.assertIsNone(fh["cells"][(-4, -4)]["vhgt"])
            ref0 = fh["cells"][(0, 0)]["refs"][0]
            self.assertEqual(ref0["base_form_key"], "000810:fallout4.esm")

            cw = fo4land.read_world_load_order([master, dlc], "Commonwealth", refs=True)
            cw_refs = {r["form_key"]: r for r in cw["cells"][(0, 0)]["refs"]}
            self.assertNotIn("000821:fallout4.esm", cw_refs)  # deleted by DLC
            self.assertIn("000820:fallout4.esm", cw_refs)
            self.assertAlmostEqual(cw_refs["000820:fallout4.esm"]["pos"][2], 96.0)  # moved by DLC
            self.assertIn("000860:dlccoast.esm", cw_refs)  # added by DLC

    def test_make_cw_overlays_dlc_world_and_water_height_build_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "inputs")
            os.makedirs(src_dir, exist_ok=True)
            master = os.path.join(src_dir, "Fallout4.esm")
            dlc = os.path.join(src_dir, "DLCCoast.esm")
            _build_master_and_dlc_plugins(master, dlc)
            sf_data = os.path.join(src_dir, "SfData")
            _write_synthetic_sf_terrain_ba2(sf_data)

            out_dir = os.path.join(tmp, "fh_stage")
            argv_prev = sys.argv
            try:
                sys.argv = [
                    "make_cw_overlays.py",
                    "build",
                    "--fo4",
                    dlc,
                    "--fo4-world",
                    "DLC03FarHarbor",
                    "--fo4-masters",
                    master,
                    "--sf-data",
                    sf_data,
                    "--out",
                    out_dir,
                    "--fo4-cells",
                    "-2",
                    "1",
                    "-2",
                    "1",
                    "--tile",
                    "4",
                    "--pad",
                    "origin",
                    "--prefix",
                    "FO4FH",
                    "--world",
                    "FO4FH_FarHarbor",
                    "--coc",
                    "FO4FH_FarHarborSpawn",
                    "--plugin",
                    "FO4WorldFarHarbor.esm",
                    "--mars-plugin",
                    "FO4WorldFarHarbor_Mars.esm",
                    "--mask-writer",
                    "builtin",
                    "--water-height-m",
                    "6.428571",
                    "--planet-min-gap-cells",
                    "2000",
                ]
                rc = mco.main()
                self.assertEqual(rc, None)

                sys.argv = [
                    "make_cw_overlays.py",
                    "check",
                    "--sf-data",
                    sf_data,
                    "--out",
                    out_dir,
                    "--no-plugins",
                ]
                self.assertEqual(mco.main(), 0)
            finally:
                sys.argv = argv_prev

            prm = json.loads(Path(out_dir, "overlays_params.json").read_text(encoding="utf-8"))
            self.assertEqual(prm["fo4_world"], "DLC03FarHarbor")
            self.assertEqual(prm["fo4_masters"], ["Fallout4.esm"])
            self.assertAlmostEqual(prm["water_height_m"], 6.428571, places=5)
            self.assertEqual(prm["planet_min_gap_cells"], 2000)
            # Spawn ground must sit above sea level (6.43 m) on the island dome!
            self.assertGreater(prm["overlays"][0]["anchor"]["local"][2], 7.4)

    def test_dotnet_fo4land_master_resolves_base_records_and_markers(self) -> None:
        if not self.dotnet or not self.fo4land_dll:
            self.skipTest(".NET SDK required")
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            out_dir = os.path.join(tmp, "out")
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(out_dir, exist_ok=True)
            master = os.path.join(src_dir, "Fallout4.esm")
            dlc = os.path.join(src_dir, "DLCCoast.esm")
            _build_master_and_dlc_plugins(master, dlc)

            # Without --master, DLC reference base 0x000810 is unresolved (type "?", empty model)
            no_master_json = os.path.join(out_dir, "no_master.json")
            r0 = subprocess.run(
                [self.dotnet, str(self.fo4land_dll), dlc, "export-exterior", "DLC03FarHarbor", "-1", "-1", "1", "1", no_master_json],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r0.returncode, 0, r0.stdout + r0.stderr)
            doc0 = json.loads(Path(no_master_json).read_text(encoding="utf-8"))
            self.assertEqual(doc0["refs"][0]["type"], "?")
            self.assertEqual(doc0["refs"][0]["model"], "")

            # With --master Fallout4.esm, base 0x000810 resolves to Static SynthCoastDock01 + model!
            with_master_json = os.path.join(out_dir, "with_master.json")
            r1 = subprocess.run(
                [self.dotnet, str(self.fo4land_dll), dlc, "--master", master, "export-exterior", "DLC03FarHarbor", "-1", "-1", "1", "1", with_master_json],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            doc1 = json.loads(Path(with_master_json).read_text(encoding="utf-8"))
            self.assertEqual(doc1["refs"][0]["type"], "Static")
            self.assertEqual(doc1["refs"][0]["base_editor_id"], "SynthCoastDock01")
            self.assertEqual(doc1["refs"][0]["model"], "Architecture\\Dock\\SynthDock01.nif")

            # Map markers with --master
            mm_json = os.path.join(out_dir, "markers.json")
            r2 = subprocess.run(
                [self.dotnet, str(self.fo4land_dll), dlc, "--master", master, "export-mapmarkers", mm_json, "DLC03FarHarbor"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            mm_doc = json.loads(Path(mm_json).read_text(encoding="utf-8"))
            self.assertEqual(len(mm_doc["markers"]), 1)
            self.assertEqual(mm_doc["markers"][0]["name"], "SynthHarbor")

            # Furniture export over master + DLC lists both furniture bases
            furn_json = os.path.join(out_dir, "furniture.json")
            r3 = subprocess.run(
                [self.dotnet, str(self.fo4land_dll), dlc, "--master", master, "export-furniture", furn_json],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
            furn_doc = json.loads(Path(furn_json).read_text(encoding="utf-8"))
            self.assertEqual(len(furn_doc["furniture"]), 2)

            # Refuses writing inside a fake git worktree
            fake_repo = os.path.join(tmp, "fake_wt")
            os.makedirs(os.path.join(fake_repo, ".git"), exist_ok=True)
            bad_out = os.path.join(fake_repo, "bad.json")
            r_bad = subprocess.run(
                [self.dotnet, str(self.fo4land_dll), dlc, "--master", master, "export-mapmarkers", bad_out, "DLC03FarHarbor"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(r_bad.returncode, 0)
            self.assertFalse(os.path.exists(bad_out))

    def test_make_core64c_world_key_and_path_guard(self) -> None:
        fh_spec = mc64.resolve_world_key("FarHarbor")
        assert fh_spec is not None
        self.assertEqual(fh_spec["source_worldspace"], "DLC03FarHarbor")
        self.assertEqual(fh_spec["plugin"], "FO4WorldFarHarbor.esm")
        self.assertEqual(fh_spec["world_edid"], "FO4FH_FarHarbor")
        self.assertEqual(fh_spec["edid_prefix"], "FO4FH_")
        self.assertEqual(fh_spec["asset_prefix"], "fo4fh")
        self.assertEqual(fh_spec["tile_cells"], 34)

        nw_spec = mc64.resolve_world_key("NukaWorld")
        assert nw_spec is not None
        self.assertEqual(nw_spec["plugin"], "FO4WorldNukaWorld.esm")
        self.assertEqual(nw_spec["world_edid"], "FO4NW_NukaWorld")
        self.assertEqual(nw_spec["edid_prefix"], "FO4NW_")
        self.assertEqual(nw_spec["tile_cells"], 40)

        with mc64.world_prefixes(fh_spec):
            self.assertEqual(mc64.door_edid("018C8B:DLCCoast.esm", "001000:DLCCoast.esm"), "FO4FH_door_018c8b_dlccoast")
        self.assertEqual(mc64.EDID_PREFIX, "FO4Core_")

        # Refuse non-buildable rows and mismatched core params
        with self.assertRaises(ValueError):
            mc64.resolve_world_key("SanctuaryHillsWorld")
        with self.assertRaises(ValueError):
            mc64.resolve_world_key("Commonwealth_DLCCoast")
        with self.assertRaises(ValueError):
            mc64.check_core_matches_world_spec({"plugin": "FO4TerrainCore.esm"}, {"world": "FO4Core_Commonwealth", "n": 64}, fh_spec)

        # Path guard refuses Git worktree and game folders
        with tempfile.TemporaryDirectory() as tmp:
            wt = os.path.join(tmp, "wt")
            os.makedirs(wt, exist_ok=True)
            Path(wt, ".git").write_text("gitdir: ../repo", encoding="utf-8")
            with self.assertRaises(OutputPathRefusedError):
                refuse_unsafe_output_path(os.path.join(wt, "sub", "out.json"))

            game_dir = os.path.join(tmp, "FakeGame")
            os.makedirs(game_dir, exist_ok=True)
            Path(game_dir, "Starfield.exe").write_bytes(b"")
            with self.assertRaises(OutputPathRefusedError):
                refuse_unsafe_output_path(os.path.join(game_dir, "Data", "out.esm"))

    def test_default_flags_commonwealth_btd_sha256_deterministic(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "inputs")
            os.makedirs(src_dir, exist_ok=True)
            master = os.path.join(src_dir, "Fallout4.esm")
            dlc = os.path.join(src_dir, "DLCCoast.esm")
            _build_master_and_dlc_plugins(master, dlc)
            sf_data = os.path.join(src_dir, "SfData")
            _write_synthetic_sf_terrain_ba2(sf_data)

            out_a = os.path.join(tmp, "cw_default_a")
            out_b = os.path.join(tmp, "cw_default_b")
            base_args = [
                "make_cw_overlays.py",
                "build",
                "--fo4",
                master,
                "--sf-data",
                sf_data,
                "--fo4-cells",
                "-2",
                "1",
                "-2",
                "1",
                "--tile",
                "4",
                "--pad",
                "origin",
                "--mask-writer",
                "builtin",
            ]
            argv_prev = sys.argv
            try:
                sys.argv = [*base_args, "--out", out_a]
                mco.main()
                sys.argv = [*base_args, "--out", out_b, "--fo4-world", "Commonwealth"]
                mco.main()
            finally:
                sys.argv = argv_prev

            for stage_out in (out_a, out_b):
                btd_bytes = Path(stage_out, "Data", "Terrain", "FO4CW3_T00.btd").read_bytes()
                mask_bytes = Path(stage_out, "Data", "textures", "terrain", "overlaymasks", "fo4cw3_t00.dds").read_bytes()
                prm_bytes = Path(stage_out, "overlays_params.json").read_bytes()
                plan_bytes = Path(stage_out, "plan.json").read_bytes()
                self.assertEqual(hashlib.sha256(btd_bytes).hexdigest(), CD03411A_DEFAULT_CW_BTD_SHA256)
                self.assertEqual(hashlib.sha256(mask_bytes).hexdigest(), CD03411A_DEFAULT_CW_MASK_SHA256)
                self.assertEqual(hashlib.sha256(prm_bytes).hexdigest(), CD03411A_DEFAULT_CW_PARAMS_SHA256)
                self.assertEqual(hashlib.sha256(plan_bytes).hexdigest(), CD03411A_DEFAULT_CW_PLAN_SHA256)


if __name__ == "__main__":
    unittest.main()
