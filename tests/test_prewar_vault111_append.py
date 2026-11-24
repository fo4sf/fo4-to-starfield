"""Offline synthetic tests verifying lossless Slot 2 PrewarVault111 append (>= 0x00EFAB) onto FO4Port.esm."""
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
for sub in ("src", "scripts/terrain"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf import navmesh as nm  # noqa: E402
from fo4sf.prewar import s1_spec, vault111_append as va  # noqa: E402
import append_prewar_vault111  # noqa: E402


def _rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0) -> bytes:
    body = b"".join(s + struct.pack("<H", len(d)) + d for s, d in subs)
    return struct.pack("<4sIIIIHH", sig, len(body), flags, fid, 0, 581, 0) + body


def _grup(label: bytes, gtype: int, payload: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload


def _synth_fo4_nvnm_bytes() -> bytes:
    verts = np.array([[0.0, 0.0, 0.0], [700.0, 0.0, 0.0], [700.0, 700.0, 0.0], [0.0, 700.0, 0.0]], dtype="<f4")
    tris = np.zeros(2, nm.TRI_DTYPE)
    tris[0] = ((0, 1, 2), (-1, -1, 1), np.float32(nm.FLT_MAX), 0, nm.F_FOUND, 0)
    tris[1] = ((0, 2, 3), (0, -1, -1), np.float32(nm.FLT_MAX), 0, nm.F_FOUND, 0)
    out = [
        struct.pack("<IIIhh", 15, nm.MAGIC, 0, 0, 0),
        struct.pack("<I", len(verts)) + verts.tobytes(),
        struct.pack("<I", len(tris)) + tris.tobytes(),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I", 0),
        struct.pack("<I8f", 1, 1.0, 1.0, *verts.min(0), *verts.max(0)),
        struct.pack("<I2h", 2, 0, 1),
    ]
    return b"".join(out)


def _synth_slot1_fo4port_esm() -> bytes:
    """Construct a synthetic Slot 1 FO4Port.esm matching 292439a5 boundaries (doors <=0xE199, museum/shell <=0xEFAA)."""
    tes4 = _rec(
        b"TES4",
        0,
        [
            (b"HEDR", struct.pack("<fII", 0.96, 12, 0x00EFAB)),
            (b"MAST", b"Starfield.esm\x00"),
            (b"DATA", b"\x00" * 8),
        ],
        flags=1,
    )
    stat_door = _rec(b"STAT", 0x0100E199, [(b"EDID", b"FO4Port_doors_anim_end\x00")])
    stat_museum = _rec(b"STAT", 0x0100E200, [(b"EDID", b"FO4Port_MuseumPiece01\x00")])
    stat_grup = _grup(b"STAT", 0, stat_door + stat_museum)

    # PrewarVault111 shell at 0x0100EFAA (exact boundary ID inside Slot 1!)
    shell_fid = 0x0100EFAA
    shell_cell = _rec(b"CELL", shell_fid, [(b"EDID", b"FO4Port_PrewarVault111\x00"), (b"DATA", struct.pack("<H", 1))])
    pers_ref = _rec(
        b"REFR",
        0x0100EFA8,
        [
            (b"EDID", b"FO4Port_PrewarShellMarker\x00"),
            (b"NAME", struct.pack("<I", 0x0100E200)),
            (b"DATA", struct.pack("<6f", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0)),
        ],
        flags=va.PERSISTENT_FLAG,
    )
    temp_ref = _rec(
        b"REFR",
        0x0100EFA9,
        [
            (b"NAME", struct.pack("<I", 0x0100E200)),
            (b"DATA", struct.pack("<6f", 4.0, 5.0, 6.0, 0.0, 0.0, 0.0)),
        ],
    )
    cell_children = _grup(
        struct.pack("<I", shell_fid),
        6,
        _grup(struct.pack("<I", shell_fid), 8, pers_ref) + _grup(struct.pack("<I", shell_fid), 9, temp_ref),
    )
    sub_grp = _grup(struct.pack("<I", 0), 3, shell_cell + cell_children)
    blk_grp = _grup(struct.pack("<I", 0), 2, sub_grp)
    cell_grup = _grup(b"CELL", 0, blk_grp)

    navi = _rec(b"NAVI", 0x01000FF1, [(b"NVER", struct.pack("<I", 12))])
    navi_grup = _grup(b"NAVI", 0, navi)
    return tes4 + stat_grup + cell_grup + navi_grup


class PrewarVault111AppendTests(unittest.TestCase):
    def test_lossless_append_respects_slot2_boundary_and_navm_conversion(self) -> None:
        base = _synth_slot1_fo4port_esm()
        self.assertEqual(va.max_local_formid(base), 0x00EFAA)

        nvnm = _synth_fo4_nvnm_bytes()
        out_bytes, rep = va.append_prewar_vault111_lossless(
            base,
            start_id=s1_spec.MIN_PREWAR_PORT_START_ID,
            fo4_navms=[(0x000CA500, nvnm), (0x000CA501, nvnm)],
            extra_persistent_specs=[
                {"edid": "PrewarExtSpawn", "pos_m": (-77.62, -3.81, 21.54), "rot_rad": (0.0, 0.0, 0.0)},
            ],
        )
        self.assertEqual(rep["base_max_local_id"], "0x00EFAA")
        self.assertEqual(rep["start_id"], "0x00EFAB")
        self.assertEqual(rep["new_cell_edid"], "FO4Port_PrewarVault111S1")
        self.assertEqual(len(rep["navm_fids"]), 2)

        ver = va.verify_lossless_append(base, out_bytes, s1_spec.MIN_PREWAR_PORT_START_ID, allow_navi_update=True)
        self.assertEqual(ver["preserved_records"], 6)  # 2 STAT + 1 CELL + 2 REFR + 1 NAVI (shell)
        self.assertGreaterEqual(ver["appended_records"], 6)

        # Verify every record <= 0x00EFAA is byte-identical except NAVI & all net-new >= 0x00EFAB
        base_map = {r.fid: r for r in va.walk_records(base) if r.sig != b"TES4"}
        out_recs = [r for r in va.walk_records(out_bytes) if r.sig != b"TES4"]
        out_map = {r.fid: r for r in out_recs}
        for fid, brec in base_map.items():
            if brec.sig == b"NAVI":
                continue
            self.assertEqual(out_map[fid].to_bytes(), brec.to_bytes())

        for fid, orec in out_map.items():
            if fid not in base_map:
                self.assertGreaterEqual(fid & 0x00FFFFFF, s1_spec.MIN_PREWAR_PORT_START_ID)

        # Verify converted NAVMs parse cleanly as Starfield v17 in metres
        navm_recs = [r for r in out_recs if r.sig == b"NAVM"]
        self.assertEqual(len(navm_recs), 2)
        for nr in navm_recs:
            nv_data = next(d for s, d in va._iter_subrecords(nr.raw_subrecords_bytes) if s == b"NVNM")  # noqa: SLF001
            parsed = nm.parse(nv_data, layout="sf")
            self.assertEqual(parsed.version, nm.SF_VERSION)
            self.assertAlmostEqual(float(parsed.vertices[1, 0]), 10.0, places=4)

    def test_rejects_low_start_id_and_mutated_slot1_record(self) -> None:
        base = _synth_slot1_fo4port_esm()
        with self.assertRaises(va.PrewarPortError):
            va.append_prewar_vault111_lossless(base, start_id=0x00EFAA)
        with self.assertRaises(va.PrewarPortError):
            va.append_prewar_vault111_lossless(base, start_id=0x00E200)

        out_bytes, _rep = va.append_prewar_vault111_lossless(base, start_id=0x00EFAB)
        corrupted = out_bytes.replace(b"FO4Port_MuseumPiece01", b"FO4Port_MuseumMutated")
        with self.assertRaises(va.PrewarPortError):
            va.verify_lossless_append(base, corrupted, 0x00EFAB, allow_navi_update=False)

    def test_append_cli_roundtrip(self) -> None:
        base = _synth_slot1_fo4port_esm()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_p = root / "FO4Port_base.esm"
            out_p = root / "FO4Port.esm"
            rep_p = root / "append_report.json"
            base_p.write_bytes(base)
            rc = append_prewar_vault111.main([
                "--base-esm", str(base_p),
                "--out-esm", str(out_p),
                "--report-json", str(rep_p),
            ])
            self.assertEqual(rc, 0)
            rep = json.loads(rep_p.read_text(encoding="utf-8"))
            self.assertEqual(rep["start_id"], "0x00EFAB")
            self.assertEqual(rep["new_cell_edid"], "FO4Port_PrewarVault111S1")


if __name__ == "__main__":
    unittest.main()
