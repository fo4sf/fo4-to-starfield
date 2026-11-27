"""Synthetic-fixture unit tests for src/fo4sf/workshop/fo4_census.py (no real game files)."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf.workshop import fo4_census  # noqa: E402


def _sub(sig: str, data: bytes) -> bytes:
    return sig.encode("latin1") + struct.pack("<H", len(data)) + data


def _rec(sig: str, fid: int, subs: list[bytes], *, compress: bool = False) -> bytes:
    payload = b"".join(subs)
    flags = 0
    if compress:
        flags = 0x00040000
        payload = struct.pack("<I", len(payload)) + zlib.compress(payload)
    return sig.encode("latin1") + struct.pack("<IIII", len(payload), flags, fid, 0) + payload[:0] + struct.pack("<I", 0) + payload


def _build_rec(sig: str, fid: int, subs: list[bytes], *, compress: bool = False) -> bytes:
    payload = b"".join(subs)
    flags = 0
    if compress:
        flags = 0x00040000
        payload = struct.pack("<I", len(payload)) + zlib.compress(payload)
    # Bethesda TES4 record header is 24 bytes: sig(4) + size(4) + flags(4) + fid(4) + rev(4) + ver_unk(4)
    return sig.encode("latin1") + struct.pack("<IIIII", len(payload), flags, fid, 0, 0) + payload


def _grup(label: str, children: list[bytes]) -> bytes:
    body = b"".join(children)
    # GRUP header is 24 bytes: "GRUP" + total_size(4) + label(4) + group_type(4) + stamp(4) + unk(4)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label.encode("latin1").ljust(4, b"\x00") + struct.pack("<III", 0, 0, 0) + body


def _make_synthetic_fo4_esm() -> bytes:
    tes4 = _build_rec("TES4", 0, [_sub("HEDR", struct.pack("<fII", 1.0, 10, 0))])

    # Keywords: base menu leaf, CC leaf, scrap filter
    kw_wood_floor = _build_rec("KYWD", 0x00100001, [_sub("EDID", b"WorkshopFilterWoodFloors\x00")])
    kw_cc_item = _build_rec("KYWD", 0x00100002, [_sub("EDID", b"WorkshopFilterCCProp\x00")])
    kw_scrap = _build_rec("KYWD", fo4_census.DEFAULT_SCRAP_FILTER_FID, [_sub("EDID", b"WorkshopRecipeFilterScrap\x00")])

    # FormLists: WorkshopMenuMain -> sub branch + CC branch (0024A0DC)
    fl_sub = _build_rec("FLST", 0x00106DA3, [
        _sub("EDID", b"WorkshopMenu01Build\x00"),
        _sub("LNAM", struct.pack("<I", 0x00100001)),
    ])
    fl_cc = _build_rec("FLST", fo4_census.DEFAULT_CC_CATEGORY_FID, [
        _sub("EDID", b"WorkshopMenu01CreationClub\x00"),
        _sub("LNAM", struct.pack("<I", 0x00100002)),
    ])
    fl_main = _build_rec("FLST", fo4_census.DEFAULT_MENU_MAIN_FID, [
        _sub("EDID", b"WorkshopMenuMain\x00"),
        _sub("LNAM", struct.pack("<I", 0x00106DA3)),
        _sub("LNAM", struct.pack("<I", fo4_census.DEFAULT_CC_CATEGORY_FID)),
    ])

    # Component (CMPO)
    cmpo_steel = _build_rec("CMPO", 0x000731A4, [
        _sub("EDID", b"c_Steel\x00"),
        _sub("GNAM", struct.pack("<I", 0x000731A5)),
    ])

    # Junk MISC with CVPA + PRPS on a STAT (compressed)
    misc_fan = _build_rec("MISC", 0x0001F908, [
        _sub("EDID", b"DeskFan\x00"),
        _sub("CVPA", struct.pack("<II", 0x000731A4, 2)),
    ])
    stat_floor = _build_rec("STAT", 0x00200010, [
        _sub("EDID", b"ShackMidFloor01\x00"),
        _sub("PRPS", struct.pack("<IfIf", 0x00000330, 1.0, 0x002233CD, 5.0)),
    ], compress=True)

    # COBJs: 1 base menu recipe, 1 CC recipe (must be excluded), 1 scrap recipe
    cobj_floor = _build_rec("COBJ", 0x00300001, [
        _sub("EDID", b"workshop_co_ShackMidFloor01\x00"),
        _sub("BNAM", struct.pack("<I", 0x00246F85)),
        _sub("CNAM", struct.pack("<I", 0x00200010)),
        _sub("FNAM", struct.pack("<I", 0x00100001)),
        _sub("FVPA", struct.pack("<II", 0x000731A4, 4)),
    ])
    cobj_cc = _build_rec("COBJ", 0x00300002, [
        _sub("EDID", b"cc_workshop_co_Prop\x00"),
        _sub("BNAM", struct.pack("<I", 0x00246F85)),
        _sub("CNAM", struct.pack("<I", 0x00200010)),
        _sub("FNAM", struct.pack("<I", 0x00100002)),
    ])
    cobj_scrap = _build_rec("COBJ", 0x00300003, [
        _sub("EDID", b"workshop_co_ScrapTree\x00"),
        _sub("CNAM", struct.pack("<I", 0x000731A4)),
        _sub("FNAM", struct.pack("<I", fo4_census.DEFAULT_SCRAP_FILTER_FID)),
        _sub("FVPA", struct.pack("<II", 0x000731A4, 5)),
    ])

    return b"".join([
        tes4,
        _grup("KYWD", [kw_wood_floor, kw_cc_item, kw_scrap]),
        _grup("FLST", [fl_sub, fl_cc, fl_main]),
        _grup("CMPO", [cmpo_steel]),
        _grup("MISC", [misc_fan]),
        _grup("STAT", [stat_floor]),
        _grup("COBJ", [cobj_floor, cobj_cc, cobj_scrap]),
    ])


class Fo4CensusTests(unittest.TestCase):
    def test_census_excludes_creation_club_and_reads_menu_prps_cmpo_junk_scrap(self) -> None:
        esm = _make_synthetic_fo4_esm()
        out = fo4_census.run_census(esm)
        self.assertEqual(out["excluded_branches"], ["WorkshopMenu01CreationClub"])
        self.assertEqual(out["counts"], {
            "menu_leaf_keywords": 1,
            "menu_recipes": 1,
            "scrap_recipes": 1,
            "components": 1,
            "junk_items": 1,
            "prps_records": 1,
        })
        self.assertEqual(out["menu_recipes"][0]["editor_id"], "workshop_co_ShackMidFloor01")
        self.assertEqual(out["scrap_recipes"][0]["editor_id"], "workshop_co_ScrapTree")
        self.assertEqual(out["prps_records"][0]["prps"][1]["value"], 5.0)
        self.assertEqual(out["junk_items"][0]["components"][0]["count"], 2)

        with tempfile.TemporaryDirectory() as tmp:
            m_path = Path(tmp) / "Fallout4.esm"
            o_path = Path(tmp) / "census.json"
            m_path.write_bytes(esm)
            rc = fo4_census.main(["--master", str(m_path), "--out", str(o_path)])
            self.assertEqual(rc, 0)
            loaded = json.loads(o_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["counts"]["menu_recipes"], 1)


if __name__ == "__main__":
    unittest.main()
