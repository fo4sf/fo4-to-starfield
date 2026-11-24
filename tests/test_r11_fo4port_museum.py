"""CI-safe and optional live-staging tests for Round 11 Step 3b + 3c (lossless FO4Port Museum extension)."""
from __future__ import annotations

import os
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_TERRAIN = REPO / "scripts" / "terrain"
SRC_DIR = REPO / "src"
for _p in (str(SRC_DIR), str(SCRIPTS_TERRAIN)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_fo4port_r11_museum as ext  # noqa: E402
from fo4sf import navmesh as navm  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402

DOC_PATH = REPO / "docs" / "terrain" / "fo4port-r11-museum-comparison.md"
PSC_PATH = REPO / "scripts" / "doors" / "FO4SF_ConfirmedLoadDoor.psc"
DRIVE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]")


# ---------------------------------------------------------------------------
# Synthetic ESM, FO4 NVNM, and BTDX v2 BA2 fixture builders (zero game files)
# ---------------------------------------------------------------------------
def _make_record(sig: bytes, fid: int, subs, flags: int = 0, version: int = 576) -> ext.RawRecord:
    body = ext.pack_subrecords(subs)
    if flags & ext.COMPRESSED_FLAG:
        body = struct.pack("<I", len(body)) + zlib.compress(body)
    return ext.RawRecord(sig, flags, fid, 0, version, 0, body)


def _make_esm(tes4: ext.RawRecord, top_grups) -> bytes:
    body = b"".join(g.to_bytes() for g in top_grups)
    provisional = tes4.to_bytes() + body
    nrec = ext.count_records_and_grups(provisional)
    # Keep original next_id from tes4
    next_id = 0x00E19A
    for ss, sp in ext.iter_subrecords(tes4.decompressed_body()):
        if ss == b"HEDR" and len(sp) == 12:
            next_id = struct.unpack("<fII", sp)[2]
    fixed_tes4 = ext.update_tes4_hedr(tes4, nrec, next_id)
    return fixed_tes4.to_bytes() + body


def _build_synthetic_base_and_source() -> tuple[bytes, bytes]:
    tes4 = _make_record(
        b"TES4",
        0,
        [
            (b"HEDR", struct.pack("<fII", 0.96, 0, 0x00E19A)),
            (b"MAST", b"Starfield.esm\x00"),
            (b"DATA", struct.pack("<Q", 0)),
        ],
        flags=1,
    )

    # Base ESM (models doors_anim_b00): max local ID = 0x00E199
    base_door = _make_record(
        b"DOOR",
        0x0100693B,
        [
            (b"EDID", b"FO4Port_paintedwooddoordoubleload01\x00"),
            (b"BFCB", b"BGSAnimationGraph_Component\x00"),
            (b"ANAM", b"AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx\x00"),
            (b"MODL", b"fo4port\\doors\\front.nif\x00"),
        ],
    )
    base_stat = _make_record(
        b"STAT",
        0x01000A10,
        [(b"EDID", b"FO4Port_SharedWall01\x00"), (b"MODL", b"fo4port\\shared_wall.nif\x00")],
    )
    base_lctn = _make_record(
        b"LCTN",
        0x0100E199,
        [(b"EDID", b"FO4Port_InteriorsLocation\x00")],
    )
    base_cell = _make_record(
        b"CELL",
        0x010011F3,
        [(b"EDID", b"FO4Port_Vault111Cryo\x00"), (b"XLCN", struct.pack("<I", 0x0100E199))],
    )
    base_anchor = _make_record(
        b"REFR",
        0x01001338,
        [(b"NAME", struct.pack("<I", 0x00000032)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))],
    )
    base_esm = _make_esm(
        tes4,
        [
            ext.TopGrup(b"DOOR", 0, 0, 0, base_door.to_bytes()),
            ext.TopGrup(b"STAT", 0, 0, 0, base_stat.to_bytes()),
            ext.TopGrup(b"CELL", 0, 0, 0, ext.wrap_cell_entry(base_cell, [base_anchor], [])),
            ext.TopGrup(b"LCTN", 0, 0, 0, base_lctn.to_bytes()),
        ],
    )

    # Source ESM (models interiors_b10): has Museum + PrewarVault111, differing body on reused DOOR,
    # net-new DOOR/STAT/TERM/TMLM/LCTN with high b10 FormIDs.
    src_door_reused_stripped = _make_record(
        b"DOOR",
        0x0100693B,
        [
            (b"EDID", b"FO4Port_paintedwooddoordoubleload01\x00"),
            (b"MODL", b"fo4port\\doors\\front.nif\x00"),
        ],
    )
    src_door_roof = _make_record(
        b"DOOR",
        0x0100E59A,
        [(b"EDID", b"FO4Port_bldwoodpdoorload01\x00"), (b"MODL", b"fo4port\\doors\\roof.nif\x00")],
    )
    src_door_gate = _make_record(
        b"DOOR",
        0x0100E59B,
        [(b"EDID", b"FO4Port_switchdoorexsmlatch02_N84C71750\x00"), (b"MODL", b"fo4port\\doors\\gate.nif\x00")],
    )
    src_stat_shared = _make_record(
        b"STAT",
        0x01000A10,
        [(b"EDID", b"FO4Port_SharedWall01\x00"), (b"MODL", b"fo4port\\shared_wall.nif\x00")],
    )
    src_stat_new = _make_record(
        b"STAT",
        0x01020001,
        [(b"EDID", b"FO4Port_MuseumPillar01\x00"), (b"MODL", b"fo4port\\pillar.nif\x00")],
    )
    src_tmlm = _make_record(
        b"TMLM",
        0x0101303F,
        [(b"EDID", b"FO4Port_tmlm_0731b1_fallout4\x00")],
    )
    src_term = _make_record(
        b"TERM",
        0x0101303E,
        [
            (b"EDID", b"FO4Port_term_0731b1_fallout4\x00"),
            (b"DNAM", struct.pack("<I", 0x0101303F)),
        ],
    )
    src_lctn_parent = _make_record(b"LCTN", 0x010405A9, [(b"EDID", b"FO4Port_InteriorsLocation\x00")])
    src_lctn_museum = _make_record(
        b"LCTN",
        0x010405D1,
        [(b"EDID", b"FO4Port_ConcordMuseumLocation\x00"), (b"PNAM", struct.pack("<I", 0x010405A9))],
    )
    src_lctn_prewar = _make_record(
        b"LCTN",
        0x010405C6,
        [(b"EDID", b"FO4Port_PrewarVault111Location\x00"), (b"PNAM", struct.pack("<I", 0x010405A9))],
    )

    museum_cell = _make_record(
        b"CELL",
        0x01012540,
        [
            (b"EDID", b"FO4Port_ConcordMuseum01\x00"),
            (b"LTMP", struct.pack("<I", 0x00006658)),
            (b"XLCN", struct.pack("<I", 0x010405D1)),
        ],
    )
    museum_pers = [
        _make_record(
            b"REFR",
            0x01012541,
            [(b"NAME", struct.pack("<I", 0x00000032)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))],
        )
    ]
    museum_temp = [
        _make_record(
            b"REFR",
            0x0101303B,
            [
                (b"NAME", struct.pack("<I", 0x0100693B)),
                (b"DATA", struct.pack("<6f", 9.142857, 0.0, -0.914286, 0, 0, 0)),
            ],
        ),
        _make_record(
            b"REFR",
            0x01013044,
            [
                (b"NAME", struct.pack("<I", 0x0100E59B)),
                (b"DATA", struct.pack("<6f", -13.714, -0.457, -3.657, 0, 0, 0)),
            ],
        ),
        _make_record(
            b"REFR",
            0x01013048,
            [
                (b"NAME", struct.pack("<I", 0x0100E59A)),
                (b"DATA", struct.pack("<6f", -21.942857, 9.142857, 9.142857, 0, 0, 0)),
            ],
        ),
        _make_record(
            b"REFR",
            0x01013050,
            [(b"NAME", struct.pack("<I", 0x01020001)), (b"DATA", struct.pack("<6f", 1, 2, 0, 0, 0, 0))],
        ),
        _make_record(
            b"REFR",
            0x01013051,
            [(b"NAME", struct.pack("<I", 0x0101303E)), (b"DATA", struct.pack("<6f", -5, 0, -3.5, 0, 0, 0))],
        ),
        _make_record(
            b"REFR",
            0x01013052,
            [(b"NAME", struct.pack("<I", 0x01000A10)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))],
        ),
    ]

    prewar_cell = _make_record(
        b"CELL",
        0x010107EA,
        [
            (b"EDID", b"FO4Port_PrewarVault111\x00"),
            (b"LTMP", struct.pack("<I", 0x00006658)),
            (b"XLCN", struct.pack("<I", 0x010405C6)),
        ],
    )
    prewar_pers = [
        _make_record(
            b"REFR",
            0x010107EB,
            [(b"NAME", struct.pack("<I", 0x00000032)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))],
        )
    ]
    prewar_temp = [
        _make_record(
            b"REFR",
            0x010107EC,
            [(b"NAME", struct.pack("<I", 0x01000A10)), (b"DATA", struct.pack("<6f", 2, 3, 0, 0, 0, 0))],
        )
    ]

    src_esm = _make_esm(
        tes4,
        [
            ext.TopGrup(
                b"DOOR",
                0,
                0,
                0,
                src_door_reused_stripped.to_bytes() + src_door_roof.to_bytes() + src_door_gate.to_bytes(),
            ),
            ext.TopGrup(b"STAT", 0, 0, 0, src_stat_shared.to_bytes() + src_stat_new.to_bytes()),
            ext.TopGrup(b"TERM", 0, 0, 0, src_term.to_bytes()),
            ext.TopGrup(
                b"CELL",
                0,
                0,
                0,
                ext.wrap_cell_entry(museum_cell, museum_pers, museum_temp)
                + ext.wrap_cell_entry(prewar_cell, prewar_pers, prewar_temp),
            ),
            ext.TopGrup(
                b"LCTN",
                0,
                0,
                0,
                src_lctn_parent.to_bytes() + src_lctn_museum.to_bytes() + src_lctn_prewar.to_bytes(),
            ),
            ext.TopGrup(b"TMLM", 0, 0, 0, src_tmlm.to_bytes()),
        ],
    )
    return base_esm, src_esm


def _build_synthetic_fo4_interior_nvnm(fo4_navm_fid: int = 0x00197BB0) -> bytes:
    """Build a valid Fallout 4 v15 interior NVNM binary payload with 2 adjacent triangles & 2 door refs."""
    verts = np.array(
        [
            [640.0, 0.0, -64.0],        # v0 near Front Door (9.143, 0.0, -0.914)
            [0.0, 200.0, 200.0],        # v1 shared atrium midpoint
            [0.0, -200.0, 200.0],       # v2 shared atrium midpoint
            [-1536.0, 640.0, 640.0],    # v3 near 3F Roof Door (-21.943, 9.143, 9.143)
        ],
        dtype=np.float32,
    )
    tris = np.zeros(2, navm.TRI_DTYPE)
    # Tri 0: (v0, v1, v2) — edge 1 (v1-v2) touches tri 1; door tri for Front Door 0x00077D22
    tris[0] = ([0, 1, 2], [-1, 1, -1], 210.0, 0, navm.F_DOOR, 0)
    # Tri 1: (v2, v1, v3) — edge 0 (v2-v1) touches tri 0; door tri for Roof Door 0x0002C1C6
    tris[1] = ([2, 1, 3], [0, -1, -1], navm.FLT_MAX, 0, navm.F_DOOR, 0)

    links = np.zeros(0, navm.LINK_DTYPE)
    doors = np.zeros(2, navm.DOOR_DTYPE)
    doors[0] = (0, navm.DOOR_EXTRA, 0x00077D22)
    doors[1] = (1, navm.DOOR_EXTRA, 0x0002C1C6)

    wps = np.zeros(1, navm.WAYPOINT_DTYPE)
    wps[0] = ([0.0, 0.0, 200.0], 0, 0)

    div, gsize, gmin, gmax, glists = navm.build_grid(verts.astype(np.float64), tris)
    out = [
        struct.pack("<IIII", 15, navm.MAGIC, 0, ext.FO4_MUSEUM_CELL_FID),
        struct.pack("<I", len(verts)),
        verts.tobytes(),
        struct.pack("<I", len(tris)),
        tris.tobytes(),
        struct.pack("<I", len(links)),
        links.tobytes(),
        struct.pack("<I", len(doors)),
        doors.tobytes(),
        struct.pack("<I", 0),  # cover
        struct.pack("<I", 0),  # cover_map
        struct.pack("<I", len(wps)),
        wps.tobytes(),
        struct.pack("<I8f", div, *gsize, *gmin, *gmax),
    ]
    for lst in glists:
        out.append(struct.pack(f"<I{len(lst)}h", len(lst), *lst))
    return b"".join(out)


def _write_synthetic_ba2_v2_gnrl(path: Path, files: list[tuple[str, bytes, bool]]) -> None:
    """Write a valid Starfield BTDX v2 GNRL archive."""
    table_size = 36 * len(files)
    payloads = []
    cur = 32 + table_size
    entries = []
    for name, raw, compress in files:
        data = zlib.compress(raw) if compress else raw
        packed = len(data) if compress else 0
        ext_b = Path(name).suffix.lstrip(".").encode("ascii")[:4].ljust(4, b"\x00")
        entries.append((zlib.crc32(name.encode()) & 0xFFFFFFFF, ext_b, 0, 0x00100100, cur, packed, len(raw), ext.BA2_ALIGN))
        payloads.append(data)
        cur += len(data)
    name_off = cur
    with path.open("wb") as f:
        f.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"GNRL", len(files), name_off, 1, 0))
        for e in entries:
            f.write(struct.pack("<I4sIIQIII", *e))
        for p in payloads:
            f.write(p)
        for name, _, _ in files:
            nb = name.encode("utf-8")
            f.write(struct.pack("<H", len(nb)) + nb)


def _write_synthetic_ba2_v2_dx10(path: Path, textures: list[tuple[str, bytes]]) -> None:
    """Write a valid Starfield BTDX v2 DX10 archive (single 4x4 BC1 mip chunk per entry)."""
    table_size = len(textures) * (24 + 24)
    cur = 32 + table_size
    entries = []
    payloads = []
    for name, raw_chunk in textures:
        z = zlib.compress(raw_chunk)
        entries.append((zlib.crc32(name.encode()) & 0xFFFFFFFF, b"dds\x00", 0, 0, 1, 24, 4, 4, 1, 71, 0, 8, cur, len(z), len(raw_chunk)))
        payloads.append(z)
        cur += len(z)
    name_off = cur
    with path.open("wb") as f:
        f.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"DX10", len(textures), name_off, 1, 0))
        for e in entries:
            f.write(struct.pack("<I4sIBBHHHBBBB", *e[:12]))
            f.write(struct.pack("<QIIHHI", e[12], e[13], e[14], 0, 0, ext.BA2_ALIGN))
        for p in payloads:
            f.write(p)
        for name, _ in textures:
            nb = name.encode("utf-8")
            f.write(struct.pack("<H", len(nb)) + nb)


# ---------------------------------------------------------------------------
# Test cases (100% CI-safe without external game data)
# ---------------------------------------------------------------------------
class TestLosslessEsmExtension(unittest.TestCase):
    def test_lossless_append_and_museum_navm(self) -> None:
        base_esm, src_esm = _build_synthetic_base_and_source()
        fo4_nvnm = _build_synthetic_fo4_interior_nvnm()

        out_esm, report = ext.extend_fo4port_esm(
            base_esm_bytes=base_esm,
            source_esm_bytes=src_esm,
            target_cells=ext.DEFAULT_CELLS,
            start_id=0x00E200,
            museum_navm_input=(fo4_nvnm, ext.FO4_MUSEUM_NAVM_FID, ext.FO4_MUSEUM_NAVM_DOOR_FALLBACKS),
        )

        ver = report["verification"]
        self.assertEqual(ver["missing_base_ids"], 0)
        self.assertEqual(ver["type_changes"], 0)
        self.assertEqual(ver["body_changes"], 0)
        self.assertEqual(ver["dangling_local_refs"], 0)
        self.assertEqual(ver["navm_count"], 1)
        self.assertEqual(ver["nvmi_count"], 1)
        self.assertEqual(ver["navm_validation_errors"], 0)
        self.assertTrue(ver["all_new_local_ids_ge_start_id"])

        # Reused DOOR 0x0100693B kept b00's BGSAnimationGraph_Component intact despite stripped source!
        self.assertEqual(len(report["reused_diff_preserved_base"]), 1)
        self.assertEqual(report["reused_diff_preserved_base"][0]["reused_base_fid"], "0x0100693B")
        out_recs = {r.fid: r for r in ext.walk_all_records(out_esm) if r.sig != b"TES4"}
        self.assertIn(b"BGSAnimationGraph_Component", out_recs[0x0100693B].decompressed_body())
        self.assertEqual([r for r in out_recs.values() if r.sig in (b"WRLD", b"PNDT")], [])

        # Both appended interior CELLs stamped with proven LTMP 0x0006BCF8 (KreetBase01LGTtemplate)
        for cname in ext.DEFAULT_CELLS:
            cinfo = report["cells"][cname]
            self.assertEqual(cinfo["ltmp"], f"0x{ext.PROVEN_INTERIOR_LTMP:08X}")
            cfid = int(cinfo["new_cell_fid"], 16)
            ltmp_sp = next(sp for ss, sp in ext.iter_subrecords(out_recs[cfid].decompressed_body()) if ss == b"LTMP")
            self.assertEqual(struct.unpack("<I", ltmp_sp)[0], ext.PROVEN_INTERIOR_LTMP)

        # Museum doors + basement gate promoted to persistent GRUP(8) (flags |= 0x400) + Novice XLOC on gate
        m_info = report["cells"]["FO4Port_ConcordMuseum01"]
        self.assertEqual(m_info["persistent_count"], 4)
        self.assertEqual(len(m_info["promoted_persistent_gate_fids"]), 1)
        gate_fid = int(m_info["promoted_persistent_gate_fids"][0], 16)
        self.assertEqual(out_recs[gate_fid].flags & 0x400, 0x400)
        gate_xloc = next(sp for ss, sp in ext.iter_subrecords(out_recs[gate_fid].decompressed_body()) if ss == b"XLOC")
        self.assertEqual(gate_xloc[0], ext.LOCK_LEVEL_NOVICE)
        self.assertIn(f"0x{gate_fid:08X}", m_info["persistent_fids"])

        # Museum NAVM matched both doors at 0.0 m and connected them via triangle_path
        nav = report["museum_navm"]
        self.assertIsNotNone(nav)
        self.assertEqual(nav["vertices"], 4)
        self.assertEqual(nav["triangles"], 2)
        self.assertEqual(nav["validation_errors"], 0)
        self.assertEqual(len(nav["doors"]), 2)
        for d in nav["doors"]:
            self.assertLessEqual(d["distance_m"], 0.001)
        self.assertEqual(len(nav["door_paths"]), 1)
        self.assertTrue(nav["door_paths"][0]["reachable"])
        self.assertEqual(nav["door_paths"][0]["hops"], 2)

        # Verify NAVI 0x00000FF1 exists and parses cleanly
        self.assertIn(ext.NAVI_FID, out_recs)
        self.assertEqual(out_recs[ext.NAVI_FID].sig, b"NAVI")

    def test_tamper_detection_refuses_any_base_mutation(self) -> None:
        base_esm, src_esm = _build_synthetic_base_and_source()
        out_esm, _ = ext.extend_fo4port_esm(base_esm, src_esm, ext.DEFAULT_CELLS, start_id=0x00E200)

        # 1. Flip 1 byte inside preserved base DOOR body (FO4Port_paintedwooddoordoubleload01 -> x)
        needle = b"SimpleOpenClose01.agx"
        idx = out_esm.find(needle)
        self.assertGreater(idx, 0)
        tampered = out_esm[:idx] + b"X" + out_esm[idx + 1 :]
        with self.assertRaises(ext.ExtensionError):
            ext.verify_lossless_extension(base_esm, tampered, start_id=0x00E200)

        # 2. Reject start_id <= max_base_local (0x00E199)
        with self.assertRaises(ext.ExtensionError):
            ext.extend_fo4port_esm(base_esm, src_esm, ext.DEFAULT_CELLS, start_id=0x00E199)


class TestLosslessBa2DeltaMerge(unittest.TestCase):
    def test_merge_gnrl_and_dx10_v2_lossless(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            b00_m = root / "b00_main.ba2"
            b10_m = root / "b10_main.ba2"
            out_m = root / "out_main.ba2"

            _write_synthetic_ba2_v2_gnrl(
                b00_m,
                [
                    ("meshes/fo4port/shared.nif", b"SHARED_NIF_BYTES_001", True),
                    ("materials/fo4port/shared.mat", b'{"tex":"textures\\\\fo4port\\\\a.dds"}', False),
                ],
            )
            _write_synthetic_ba2_v2_gnrl(
                b10_m,
                [
                    ("meshes/fo4port/shared.nif", b"MODIFIED_SHOULD_NOT_OVERRIDE", True),
                    ("meshes/fo4port/museum_roof.nif", b"MUSEUM_ROOF_NIF_BYTES_002", True),
                    ("meshes/fo4port/unrelated.nif", b"UNRELATED_BULK_IGNORED", True),
                ],
            )

            res_m = ext.merge_ba2_v2_lossless(
                b00_m,
                [(b10_m, ["meshes\\fo4port\\shared.nif", "meshes\\fo4port\\museum_roof.nif"])],
                out_m,
            )
            self.assertEqual(res_m["base_entries"], 2)
            self.assertEqual(res_m["added_entries"], 1)  # shared.nif deduplicated!
            self.assertEqual(res_m["total_entries"], 3)

            ba2_m = Ba2(str(out_m))
            self.assertEqual(ba2_m.read("meshes/fo4port/shared.nif"), b"SHARED_NIF_BYTES_001")
            self.assertEqual(ba2_m.read("meshes/fo4port/museum_roof.nif"), b"MUSEUM_ROOF_NIF_BYTES_002")
            self.assertIsNone(ba2_m.find("meshes/fo4port/unrelated.nif"))

            # DX10 texture delta from 2 source archives merged into 1 output archive
            b00_t = root / "b00_tex.ba2"
            b10_t1 = root / "b10_tex1.ba2"
            b10_t2 = root / "b10_tex2.ba2"
            out_t = root / "out_tex.ba2"
            _write_synthetic_ba2_v2_dx10(b00_t, [("textures/fo4port/a.dds", b"\x11" * 16)])
            _write_synthetic_ba2_v2_dx10(b10_t1, [("textures/fo4port/museum_brick.dds", b"\x22" * 16)])
            _write_synthetic_ba2_v2_dx10(b10_t2, [("textures/fo4port/museum_trim.dds", b"\x33" * 16)])

            res_t = ext.merge_ba2_v2_lossless(
                b00_t,
                [
                    (b10_t1, ["textures\\fo4port\\museum_brick.dds"]),
                    (b10_t2, ["textures\\fo4port\\museum_trim.dds"]),
                ],
                out_t,
            )
            self.assertEqual(res_t["base_entries"], 1)
            self.assertEqual(res_t["added_entries"], 2)
            self.assertEqual(res_t["total_entries"], 3)
            ba2_t = Ba2(str(out_t))
            self.assertTrue(ba2_t.read("textures/fo4port/a.dds").endswith(b"\x11" * 16))
            self.assertTrue(ba2_t.read("textures/fo4port/museum_brick.dds").endswith(b"\x22" * 16))
            self.assertTrue(ba2_t.read("textures/fo4port/museum_trim.dds").endswith(b"\x33" * 16))

            # Exceeding max_size_bytes must raise ExtensionError
            with self.assertRaises(ext.ExtensionError):
                ext.merge_ba2_v2_lossless(b00_t, [(b10_t1, ["textures\\fo4port\\museum_brick.dds"])], out_t, max_size_bytes=64)


class TestConfirmedLoadDoorAndDocs(unittest.TestCase):
    def test_confirmed_load_door_papyrus_contract(self) -> None:
        raw = PSC_PATH.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "PSC must not have UTF-8 BOM")
        txt = raw.decode("utf-8")
        self.assertIsNone(DRIVE_PATH_RE.search(txt), "PSC must not contain local drive paths")

        self.assertNotIn("Utility.Wait(", txt, "FO4SF_ConfirmedLoadDoor must be non-blocking (StartTimer/OnTimer)")

        for required in (
            "Scriptname FO4SF_ConfirmedLoadDoor extends ObjectReference",
            "Event OnInit()",
            "Event OnLoad()",
            "Event OnCellAttach()",
            "Event OnActivate(ObjectReference akActionRef)",
            "Event OnTimer(int aiTimerID)",
            "if akActionRef != None && akActionRef != player",
            "StartTimer(GetPollInterval(), TIMER_ARRIVAL)",
            "bool Function IsTransitionReady(Actor player, Cell beforeCell, Cell anchorCell, bool isOut)",
            "bool Function NeedsMoveTo(Actor player, Cell anchorCell, bool isOut)",
            "(anchorCell != None && curCell == anchorCell) || (anchorCell == None && curCell != beforeCell)",
            "player.MoveTo(activeAnchor, 0.0, 0.0, 0.0, True, False)",
            "player.SetPosition(activeTx, activeTy, activeTz)",
            "player.SetAngle(0.0, 0.0, DestinationHeading)",
            "afterCell.GetFormID() / 16777216",
            "anchor.GetFormID() / 16777216",
            "player.Is3DLoaded()",
            "player.IsInInterior()",
            "Game.GetFormFromFile(TargetFormId, TargetPlugin)",
            "FallbackTargetPlugin",
            "FallbackTargetFormId",
            "FO4SF_LOADDOOR init",
            "FO4SF_LOADDOOR attached",
            "FO4SF_LOADDOOR activate_begin",
            "FO4SF_LOADDOOR confirmed",
            "FO4SF_LOADDOOR failed",
            "surface_cell_not_core",
            "position_not_confirmed",
        ):
            self.assertIn(required, txt, f"missing contract token: {required}")

    def test_p1_exterior_exit_coords_within_core_4096_grid(self) -> None:
        # FO4TerrainCore.esm exterior grid spans XCLC -32..31 in X and Y at 100.0 m per cell.
        import math

        for label, local_xy, merged_xy, exp_local_cell, exp_merged_cell in (
            ("p1_front_out", (-812.50, 1002.06), (-2012.50, -1697.94), (-9, 10), (-21, -17)),
            ("p1_roof_out", (-808.49, 977.61), (-2008.49, -1722.39), (-9, 9), (-21, -18)),
        ):
            lc = (math.floor(local_xy[0] / 100.0), math.floor(local_xy[1] / 100.0))
            mc = (math.floor(merged_xy[0] / 100.0), math.floor(merged_xy[1] / 100.0))
            self.assertEqual(lc, exp_local_cell, label)
            self.assertEqual(mc, exp_merged_cell, label)
            for cx, cy in (lc, mc):
                self.assertTrue(-32 <= cx <= 31 and -32 <= cy <= 31, f"{label} cell {(cx, cy)} out of -32..31")

    def test_comparison_doc_hygiene_and_metrics(self) -> None:
        raw = DOC_PATH.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "doc must not have UTF-8 BOM")
        txt = raw.decode("utf-8")
        self.assertIsNone(DRIVE_PATH_RE.search(txt), "doc must not leak local Windows drive paths")
        for token in (
            "OFFLINE ONLY — UNPROVEN IN GAME",
            "FO4Port_ConcordMuseum01",
            "FO4Port_PrewarVault111",
            "0x0100E2F4",
            "0x0100EDF0",
            "0x0100EFA8",
            "0x00000FF1",
            "0x0006BCF8",
            "KreetBase01LGTtemplate",
            "0x01000DEF",
            "0x01000DEE",
            "0x0001C903",
            "ConcordMuseumTemplate",
            "StartTimer",
            "master index 0x00",
            "0x0100693B",
            "0x01001319",
            "0x01001616",
            "0x01001618",
            "0x0100E0E6",
            "0x0100126E",
            "FO4SFNewGame.esm",
            "FO4SFVaultGearDoor.esm",
            "FO4SFExitLift.esm",
            "FO4SFMapMarkers.esm",
            "FO4SFMission.esm",
            "FO4SF_ConfirmedLoadDoor.psc",
            "switchdoorexsmlatch02",
        ):
            self.assertIn(token, txt, f"doc missing required section/token: {token}")


# ---------------------------------------------------------------------------
# Optional live-staging PC verification (skipped cleanly on hosted Linux CI)
# ---------------------------------------------------------------------------
_LIVE_B00 = os.environ.get("FO4SF_R11_B00_DIR", "")
_LIVE_B10 = os.environ.get("FO4SF_R11_B10_DIR", "")
_LIVE_FO4 = os.environ.get("FO4SF_R11_FO4_ESM", "")
_LIVE_READY = bool(
    _LIVE_B00
    and _LIVE_B10
    and _LIVE_FO4
    and (Path(_LIVE_B00) / "FO4Port.esm").is_file()
    and (Path(_LIVE_B10) / "FO4Port.esm").is_file()
    and Path(_LIVE_FO4).is_file()
)


@unittest.skipUnless(_LIVE_READY, "live PC staging env vars not configured (skipped on CI)")
class TestLivePcStagingExtension(unittest.TestCase):
    def test_live_b00_plus_b10_lossless_and_museum_navm(self) -> None:
        base_bytes = (Path(_LIVE_B00) / "FO4Port.esm").read_bytes()
        src_bytes = (Path(_LIVE_B10) / "FO4Port.esm").read_bytes()
        nvnm_raw, fo4_doors = ext.read_fo4_interior_navm_and_doors(Path(_LIVE_FO4))

        out_esm, rep = ext.extend_fo4port_esm(
            base_esm_bytes=base_bytes,
            source_esm_bytes=src_bytes,
            target_cells=ext.DEFAULT_CELLS,
            start_id=ext.DEFAULT_START_ID,
            museum_navm_input=(nvnm_raw, ext.FO4_MUSEUM_NAVM_FID, fo4_doors),
        )
        ver = rep["verification"]
        self.assertEqual(ver["base_non_tes4_records"], 55071)
        self.assertEqual(ver["missing_base_ids"], 0)
        self.assertEqual(ver["type_changes"], 0)
        self.assertEqual(ver["body_changes"], 0)
        self.assertEqual(ver["dangling_local_refs"], 0)
        self.assertEqual(ver["navm_validation_errors"], 0)
        self.assertEqual(len(rep["museum_navm"]["doors"]), 3)
        self.assertTrue(all(p["reachable"] for p in rep["museum_navm"]["door_paths"]))
        self.assertEqual(rep["cells"]["FO4Port_ConcordMuseum01"]["ltmp"], f"0x{ext.PROVEN_INTERIOR_LTMP:08X}")
        self.assertEqual(rep["cells"]["FO4Port_PrewarVault111"]["ltmp"], f"0x{ext.PROVEN_INTERIOR_LTMP:08X}")
        pers_fids = rep["cells"]["FO4Port_ConcordMuseum01"]["persistent_fids"]
        for expected_pers in ("0x0100E2F5", "0x0100EDF0", "0x0100E35E", "0x0100EDEC", "0x0100EDF5", "0x0100EDF2", "0x0100E3B6"):
            self.assertIn(expected_pers, pers_fids)
        syn = rep["cells"]["FO4Port_ConcordMuseum01"]["synthesized_doors"]
        self.assertIn("FO4Port_PrestonDoorREF", syn)
        self.assertIn("FO4Port_PrestonExitDoor", syn)
        out_recs = {r.fid: r for r in ext.walk_all_records(out_esm) if r.sig != b"TES4"}
        self.assertEqual(out_recs[0x0100EDF0].flags & 0x400, 0x400)
        self.assertEqual(out_recs[0x0100E35E].flags & 0x400, 0x400)
        gate_xloc = next(sp for ss, sp in ext.iter_subrecords(out_recs[0x0100EDF0].decompressed_body()) if ss == b"XLOC")
        self.assertEqual(gate_xloc[0], ext.LOCK_LEVEL_NOVICE)
        term_xloc = next(sp for ss, sp in ext.iter_subrecords(out_recs[0x0100E35E].decompressed_body()) if ss == b"XLOC")
        self.assertEqual(term_xloc[0], ext.LOCK_LEVEL_NOVICE)
        term_xlkr = next(sp for ss, sp in ext.iter_subrecords(out_recs[0x0100E35E].decompressed_body()) if ss == b"XLKR")
        self.assertEqual(struct.unpack_from("<II", term_xlkr, 0), (0, 0x0100EDF0))
        self.assertEqual([r for r in out_recs.values() if r.sig in (b"WRLD", b"PNDT")], [])


if __name__ == "__main__":
    unittest.main()
