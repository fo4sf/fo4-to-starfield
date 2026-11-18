"""Offline synthetic unit tests for `scripts/terrain/fo4_world_census.py` and `scripts/terrain/sf_location_census.py`."""
from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import unittest
import zlib

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
if os.path.join(REPO, "scripts", "terrain") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))

from fo4sf import fo4land as fl  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import fo4_world_census as fwc  # noqa: E402
import sf_location_census as slc  # noqa: E402


def _sub(sig: bytes, payload: bytes) -> bytes:
    return sig + struct.pack("<H", len(payload)) + payload


def _rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0, compress: bool = False) -> bytes:
    raw = b"".join(_sub(s, d) for s, d in subs)
    if compress:
        raw = struct.pack("<I", len(raw)) + zlib.compress(raw)
        flags |= fl.COMPRESSED
    return struct.pack("<4sIIIIHH", sig, len(raw), flags, fid, 0, 131, 0) + raw


def _grup(label: bytes, gtype: int, body: bytes) -> bytes:
    return struct.pack("<4sI4siII", b"GRUP", 24 + len(body), label, gtype, 0, 0) + body


def _tes4_header(masters: list[str] = ()) -> bytes:
    subs = [
        (b"HEDR", struct.pack("<fII", 1.0, 1, 0x800)),
        *[(b"MAST", m.encode("ascii") + b"\0") for m in masters],
    ]
    return _rec(b"TES4", 0, subs, flags=0x01)


class WorldCensusTests(unittest.TestCase):
    def _build_fo4_fixtures(self, directory: str) -> tuple[str, str]:
        os.makedirs(directory, exist_ok=True)
        fo4_path = os.path.join(directory, "Fallout4.esm")
        dlc_path = os.path.join(directory, "DLCCoast.esm")

        # Secret display prose that MUST NEVER leak into census output (Rule R4)
        forbidden_prose = b"PROSE_DO_NOT_EMIT_IN_CENSUS\0"

        # Base Fallout4.esm records
        door_grp = _grup(
            b"DOOR",
            0,
            _rec(b"DOOR", 0x000100, [(b"EDID", b"TestLoadDoor\0"), (b"FULL", forbidden_prose)]),
        )
        lctn_grp = _grup(
            b"LCTN",
            0,
            b"".join(
                [
                    _rec(b"LCTN", 0x002CF0, [(b"EDID", b"CommonwealthLocation\0"), (b"FULL", forbidden_prose)]),
                    _rec(
                        b"LCTN",
                        0x002CF1,
                        [
                            (b"EDID", b"DiamondCityLocation\0"),
                            (b"PNAM", struct.pack("<I", 0x002CF0)),
                            (b"FULL", forbidden_prose),
                        ],
                    ),
                    _rec(b"LCTN", 0x003979, [(b"EDID", b"DCInteriorOnlyLocation\0")]),
                ]
            ),
        )
        eczn_grp = _grup(
            b"ECZN",
            0,
            _rec(
                b"ECZN",
                0x004000,
                [(b"EDID", b"CWZone01\0"), (b"DATA", struct.pack("<IIBBBB", 0, 0x002CF0, 0, 1, 0, 10))],
            ),
        )
        regn_grp = _grup(
            b"REGN",
            0,
            _rec(b"REGN", 0x005000, [(b"EDID", b"CWRegion01\0"), (b"WNAM", struct.pack("<I", 0x00003C))]),
        )

        # Interior cell linked by load door from DiamondCity
        int_cell = _rec(
            b"CELL",
            0x006000,
            [
                (b"EDID", b"DCInteriorCell01\0"),
                (b"DATA", struct.pack("<H", 0x0001)),
                (b"XLCN", struct.pack("<I", 0x003979)),
            ],
        )
        int_children = _grup(
            struct.pack("<I", 0x006000),
            6,
            _grup(
                struct.pack("<I", 0x006000),
                8,
                b"".join(
                    [
                        _rec(
                            b"REFR",
                            0x006001,
                            [
                                (b"NAME", struct.pack("<I", 0x000100)),
                                (b"XTEL", struct.pack("<I", 0x007102)),
                            ],
                        ),
                        _rec(
                            b"REFR",
                            0x006002,
                            [(b"NAME", struct.pack("<I", 0x000010)), (b"XMRK", b""), (b"FULL", forbidden_prose)],
                        ),
                    ]
                ),
            ),
        )
        cell_top = _grup(b"CELL", 0, _grup(b"\0\0\0\0", 2, _grup(b"\0\0\0\0", 3, int_cell + int_children)))

        # Commonwealth WRLD 0x00003C + persistent cell + exterior cells (-2, -1) and (4, 5)
        steps_dry = np.full((33, 33), 20, dtype=np.int64)   # 8 * 20 = 160 units = 2.29 m (> 0.5 m dry)
        steps_wet = np.full((33, 33), -20, dtype=np.int64)  # -2.29 m (< 0.5 m wet)
        vhgt_dry = fl.encode_vhgt(0.0, steps_dry)
        vhgt_wet = fl.encode_vhgt(0.0, steps_wet)

        cw_pers_cell = _rec(b"CELL", 0x007000, [(b"EDID", b"CWPersistent\0")])
        cw_pers_grp = _grup(
            struct.pack("<I", 0x007000),
            6,
            _grup(
                struct.pack("<I", 0x007000),
                8,
                b"".join(
                    [
                        # Map marker
                        _rec(
                            b"REFR",
                            0x007010,
                            [
                                (b"NAME", struct.pack("<I", 0x000010)),
                                (b"XMRK", b""),
                                (b"FULL", forbidden_prose),
                            ],
                        ),
                        # Door Commonwealth -> DiamondCity
                        _rec(
                            b"REFR",
                            0x007011,
                            [
                                (b"NAME", struct.pack("<I", 0x000100)),
                                (b"XTEL", struct.pack("<I", 0x007101)),
                            ],
                        ),
                        # Ref that DLC will delete
                        _rec(b"REFR", 0x007099, [(b"NAME", struct.pack("<I", 0x000100))]),
                    ]
                ),
            ),
        )
        cw_c1 = _rec(b"CELL", 0x007020, [(b"XCLC", struct.pack("<ii", -2, -1))])
        cw_c1_grp = _grup(
            struct.pack("<I", 0x007020),
            6,
            _grup(
                struct.pack("<I", 0x007020),
                9,
                b"".join(
                    [
                        _rec(b"LAND", 0x007021, [(b"VHGT", vhgt_dry)]),
                        _rec(b"REFR", 0x007022, [(b"NAME", struct.pack("<I", 0x000100))]),
                    ]
                ),
            ),
        )
        cw_c2 = _rec(b"CELL", 0x007030, [(b"XCLC", struct.pack("<ii", 4, 5))])
        cw_c2_grp = _grup(
            struct.pack("<I", 0x007030),
            6,
            _grup(struct.pack("<I", 0x007030), 9, _rec(b"LAND", 0x007031, [(b"VHGT", vhgt_wet)])),
        )
        cw_wrld = _rec(
            b"WRLD",
            0x00003C,
            [
                (b"EDID", b"Commonwealth\0"),
                (b"FULL", forbidden_prose),
                (b"XLCN", struct.pack("<I", 0x002CF0)),
                (b"DNAM", struct.pack("<ff", -2048.0, 0.0)),
            ],
        )
        cw_children = _grup(
            struct.pack("<I", 0x00003C),
            1,
            cw_pers_cell
            + cw_pers_grp
            + _grup(b"\0\0\0\0", 4, _grup(b"\0\0\0\0", 5, cw_c1 + cw_c1_grp + cw_c2 + cw_c2_grp)),
        )

        # DiamondCity WRLD 0x000F94 (child of Commonwealth)
        dc_pers = _rec(b"CELL", 0x007100, [(b"EDID", b"DCPersistent\0")])
        dc_pers_grp = _grup(
            struct.pack("<I", 0x007100),
            6,
            _grup(
                struct.pack("<I", 0x007100),
                8,
                b"".join(
                    [
                        # Door DiamondCity -> Commonwealth
                        _rec(
                            b"REFR",
                            0x007101,
                            [(b"NAME", struct.pack("<I", 0x000100)), (b"XTEL", struct.pack("<I", 0x007011))],
                        ),
                        # Door DiamondCity -> DCInteriorCell01
                        _rec(
                            b"REFR",
                            0x007102,
                            [(b"NAME", struct.pack("<I", 0x000100)), (b"XTEL", struct.pack("<I", 0x006001))],
                        ),
                    ]
                ),
            ),
        )
        dc_wrld = _rec(
            b"WRLD",
            0x000F94,
            [
                (b"EDID", b"DiamondCity\0"),
                (b"WNAM", struct.pack("<I", 0x00003C)),
                (b"XLCN", struct.pack("<I", 0x002CF1)),
            ],
        )
        dc_children = _grup(struct.pack("<I", 0x000F94), 1, dc_pers + dc_pers_grp)
        wrld_top = _grup(b"WRLD", 0, cw_wrld + cw_children + dc_wrld + dc_children)

        with open(fo4_path, "wb") as f:
            f.write(_tes4_header() + door_grp + lctn_grp + eczn_grp + regn_grp + cell_top + wrld_top)

        # DLCCoast.esm (master Fallout4.esm -> index 00, own records index 01)
        dlc_lctn = _grup(
            b"LCTN",
            0,
            _rec(b"LCTN", 0x01000800, [(b"EDID", b"DLC03FarHarborLocation\0"), (b"FULL", forbidden_prose)]),
        )
        # Override Commonwealth: delete 0x007099, add 2 boat doors to Far Harbor
        dlc_cw_pers = _rec(b"CELL", 0x00007000, [(b"EDID", b"CWPersistent\0")])
        dlc_cw_pers_grp = _grup(
            struct.pack("<I", 0x00007000),
            6,
            _grup(
                struct.pack("<I", 0x00007000),
                8,
                b"".join(
                    [
                        _rec(b"REFR", 0x00007099, [], flags=fwc.DELETED),
                        _rec(
                            b"REFR",
                            0x01000901,
                            [(b"NAME", struct.pack("<I", 0x00000100)), (b"XTEL", struct.pack("<I", 0x01000A01))],
                        ),
                        _rec(
                            b"REFR",
                            0x01000902,
                            [(b"NAME", struct.pack("<I", 0x00000100)), (b"XTEL", struct.pack("<I", 0x01000A02))],
                        ),
                    ]
                ),
            ),
        )
        dlc_cw_wrld = _rec(b"WRLD", 0x0000003C, [(b"EDID", b"Commonwealth\0")])
        dlc_cw_children = _grup(struct.pack("<I", 0x0000003C), 1, dlc_cw_pers + dlc_cw_pers_grp)

        # DLC03FarHarbor WRLD 0x01000B0F with 2 return boat doors + land bounds [-29, 20, -21, 31]
        fh_pers = _rec(b"CELL", 0x01000A00, [(b"EDID", b"FHPersistent\0")])
        fh_pers_grp = _grup(
            struct.pack("<I", 0x01000A00),
            6,
            _grup(
                struct.pack("<I", 0x01000A00),
                8,
                b"".join(
                    [
                        _rec(
                            b"REFR",
                            0x01000A01,
                            [(b"NAME", struct.pack("<I", 0x00000100)), (b"XTEL", struct.pack("<I", 0x01000901))],
                        ),
                        _rec(
                            b"REFR",
                            0x01000A02,
                            [(b"NAME", struct.pack("<I", 0x00000100)), (b"XTEL", struct.pack("<I", 0x01000902))],
                        ),
                        _rec(
                            b"REFR",
                            0x01000A03,
                            [(b"NAME", struct.pack("<I", 0x00000010)), (b"XMRK", b"")],
                        ),
                    ]
                ),
            ),
        )
        fh_c1 = _rec(b"CELL", 0x01000B10, [(b"XCLC", struct.pack("<ii", -29, -21))])
        fh_c1_grp = _grup(
            struct.pack("<I", 0x01000B10),
            6,
            _grup(struct.pack("<I", 0x01000B10), 9, _rec(b"LAND", 0x01000B11, [(b"VHGT", vhgt_dry)], compress=True)),
        )
        fh_c2 = _rec(b"CELL", 0x01000B20, [(b"XCLC", struct.pack("<ii", 20, 31))])
        fh_c2_grp = _grup(
            struct.pack("<I", 0x01000B20),
            6,
            _grup(struct.pack("<I", 0x01000B20), 9, _rec(b"LAND", 0x01000B21, [(b"VHGT", vhgt_dry)])),
        )
        fh_wrld = _rec(
            b"WRLD",
            0x01000B0F,
            [
                (b"EDID", b"DLC03FarHarbor\0"),
                (b"XLCN", struct.pack("<I", 0x01000800)),
            ],
        )
        fh_children = _grup(
            struct.pack("<I", 0x01000B0F),
            1,
            fh_pers + fh_pers_grp + _grup(b"\0\0\0\0", 4, _grup(b"\0\0\0\0", 5, fh_c1 + fh_c1_grp + fh_c2 + fh_c2_grp)),
        )
        dlc_wrld_top = _grup(b"WRLD", 0, dlc_cw_wrld + dlc_cw_children + fh_wrld + fh_children)

        with open(dlc_path, "wb") as f:
            f.write(_tes4_header(["Fallout4.esm"]) + dlc_lctn + dlc_wrld_top)

        return fo4_path, dlc_path

    def _build_sf_fixtures(self, directory: str) -> tuple[str, str, str]:
        os.makedirs(directory, exist_ok=True)
        sf_path = os.path.join(directory, "Starfield.esm")
        core_path = os.path.join(directory, "FO4TerrainCore.esm")
        reg_path = os.path.join(directory, "FO4TerrainCore_Mars.esm")

        forbidden_lscr_text = b"LOADING_SCREEN_TIP_PROSE_FORBIDDEN\0"

        sf_w = esm.PluginWriter([], flags=esm.ESM)
        sf_w.add(esm.Record(b"STDT", 0x000011, [(b"EDID", esm.zbytes("Sol"))]))
        sf_w.add(esm.Record(b"PNDT", 0x03F59A, [(b"EDID", esm.zbytes("MarsPlanetData"))]))
        sf_w.add(esm.Record(b"BIOM", 0x2A3777, [(b"EDID", esm.zbytes("DesertRockyNoLifeMars"))]))
        sf_w.add(esm.Record(b"PCMT", 0x010001, [(b"EDID", esm.zbytes("PCMTree01"))]))
        sf_w.add(esm.Record(b"PCBN", 0x010002, [(b"EDID", esm.zbytes("PCMBranch01"))]))
        sf_w.add(esm.Record(b"PCCN", 0x010003, [(b"EDID", esm.zbytes("PCMContent01"))]))
        sf_w.add(esm.Record(b"PKIN", 0x010004, [(b"EDID", esm.zbytes("PackIn01"))]))
        sf_w.add(
            esm.Record(
                b"LSCR",
                0x020001,
                [
                    (b"EDID", esm.zbytes("LoadScreen01")),
                    (b"DESC", forbidden_lscr_text),
                    (b"CTDA", b"\0" * 32),
                ],
            )
        )
        # Lever keywords
        levers = [
            (0x1984BD, "PCM_OverlayExclusionZone"),
            (0x0C21AD, "PCM_OverlayExclusionZone_HumanLocations"),
            (0x11D575, "LocTypeNoPCMScanTreeContent"),
            (0x2194F4, "LocTypeNoPCMCreatureContent"),
            (0x2253D1, "LocTypeSENotAllowed"),
            (0x1EF941, "LocTypeNoHumanPresence"),
            (0x2CA99D, "LocTypeOverlay"),
        ]
        for kfid, kedid in levers:
            sf_w.add(esm.Record(b"KYWD", kfid, [(b"EDID", esm.zbytes(kedid))]))

        # SSol + SSol_PMars + SSol_PMars_Surface
        sf_w.add(esm.Record(b"LCTN", 0x061527, [(b"EDID", esm.zbytes("SSol"))]))
        sf_w.add(
            esm.Record(
                b"LCTN",
                0x01B735,
                [(b"EDID", esm.zbytes("SSol_PMars")), (b"PNAM", struct.pack("<I", 0x061527))],
            )
        )
        sf_w.add(
            esm.Record(
                b"LCTN",
                0x01B736,
                [
                    (b"EDID", esm.zbytes("SSol_PMars_Surface")),
                    (b"PNAM", struct.pack("<I", 0x01B735)),
                    (b"KWDA", struct.pack("<2I", 0x2CA99D, 0x2253D1)),
                ],
            )
        )

        # Build WRLD group with LC172World + map marker child
        lc172_rec = esm.Record(
            b"WRLD",
            0x02DF8C,
            [
                (b"EDID", esm.zbytes("LC172World")),
                (b"BFCB", esm.zbytes("BGSWorldSpaceOverlay_Component")),
                (b"SNAM", struct.pack("<i", 0)),
                (b"PNAM", struct.pack("<i", 4)),
                (b"BNAM", struct.pack("<I", 0x102382)),
                (b"BFCE", b""),
                (b"DATA", b"\x01"),
                (b"FNAM", b"\x00"),
            ],
        )
        mm_cell = esm.Record(b"CELL", 0x02DF8D, [(b"EDID", esm.zbytes("LC172Pers"))]).to_bytes()
        mm_ref = esm.Record(
            b"REFR",
            0x3E5E12,
            [(b"NAME", struct.pack("<I", 0x000010)), (b"FULL", forbidden_lscr_text)],
        ).to_bytes(compress=True)
        lc172_children = _grup(
            struct.pack("<I", 0x02DF8C),
            1,
            mm_cell + _grup(struct.pack("<I", 0x02DF8D), 6, _grup(struct.pack("<I", 0x02DF8D), 8, mm_ref)),
        )
        sf_bytes = sf_w.to_bytes(compress=False) + _grup(b"WRLD", 0, lc172_rec.to_bytes() + lc172_children)
        with open(sf_path, "wb") as f:
            f.write(sf_bytes)

        # Synthetic FO4TerrainCore.esm
        core_w = esm.PluginWriter(["Starfield.esm"], flags=esm.ESM)
        core_w.add(
            esm.Record(
                b"SFBK",
                core_w.own(0x801),
                [
                    (b"EDID", esm.zbytes("FO4Core_CommonwealthBlock")),
                    (b"ANAM", esm.zbytes("Data\\TERRAIN\\FO4Core_Commonwealth.btd")),
                    (b"DNAM", struct.pack("<2I", 64, 64)),
                    (b"ENAM", struct.pack("<2f", -120.0, 503.0)),
                    (b"INAM", b"\x01"),
                ],
            )
        )
        core_w.add(
            esm.Record(
                b"LCTN",
                core_w.own(0x802),
                [
                    (b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")),
                    (b"PNAM", struct.pack("<I", 0x01B736)),
                    (b"KWDA", struct.pack("<I", 0x2CA99D)),
                ],
            )
        )
        core_w.add(
            esm.Record(
                b"WRLD",
                core_w.own(0x803),
                [
                    (b"EDID", esm.zbytes("FO4Core_Commonwealth")),
                    (b"BFCB", esm.zbytes("BGSWorldSpaceOverlay_Component")),
                    (b"SNAM", struct.pack("<i", 0)),
                    (b"PNAM", struct.pack("<i", 4)),
                    (b"BNAM", struct.pack("<I", core_w.own(0x801))),
                    (b"BFCE", b""),
                    (b"BNAM", struct.pack("<I", 0x2A3777)),
                    (b"DATA", b"\x01"),
                    (b"FNAM", b"\x00"),
                    (b"DNAM", struct.pack("<2f", -2048.0, -200.0)),
                ],
            )
        )
        core_w.write(core_path, compress=False)

        # Synthetic FO4TerrainCore_Mars.esm
        reg_w = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], flags=esm.ESM)
        reg_w.add(
            esm.Record(
                b"PNDT",
                0x03F59A,
                [
                    (b"EDID", esm.zbytes("MarsPlanetData")),
                    (b"CNAM", struct.pack("<ddI", 0.3, -1.2, 0x01000803)),
                    (b"BDST", b""),
                    (b"BDED", b""),
                ],
            )
        )
        reg_w.write(reg_path, compress=False)
        return sf_path, core_path, reg_path

    def test_fo4_census_synthetic_load_order_and_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fo4_esm, dlc_esm = self._build_fo4_fixtures(os.path.join(tmp, "inputs"))
            out_json = os.path.join(tmp, "out", "fo4_census.json")
            rc = fwc.main(["--out", out_json, fo4_esm, dlc_esm])
            self.assertEqual(rc, 0)
            with open(out_json, encoding="utf-8") as f:
                raw_text = f.read()
            self.assertNotIn("PROSE_DO_NOT_EMIT_IN_CENSUS", raw_text)
            doc = json.loads(raw_text)

            self.assertEqual(doc["totals"]["worlds"], 3)
            self.assertEqual(doc["totals"]["lctn"], 4)
            self.assertEqual(doc["totals"]["lctn_unassigned_world"], 0)
            self.assertEqual(doc["totals"]["eczn"], 1)
            self.assertEqual(doc["totals"]["regn"], 1)
            self.assertEqual(doc["totals"]["map_markers_worldspace"], 2)
            self.assertEqual(doc["totals"]["map_markers_interior"], 1)

            cw = doc["worlds"]["Commonwealth"]
            self.assertEqual(cw["land_cells"], 2)
            self.assertEqual(cw["land_bbox"], [-2, 4, -1, 5])
            self.assertEqual(cw["dry_cells"], 1)
            self.assertEqual(cw["dry_bbox"], [-2, -2, -1, -1])
            self.assertEqual(cw["ref_bbox"], [-2, -2, -1, -1])
            # 0x7099 was deleted by DLCCoast.esm -> 1 marker + 1 DC door + 2 FH boat doors + 1 ext ref = 5 placed refs
            self.assertEqual(cw["placed_refs"], 5)

            fh = doc["worlds"]["DLC03FarHarbor"]
            self.assertEqual(fh["land_bbox"], [-29, 20, -21, 31])
            self.assertEqual(fh["map_markers"], 1)

            pairs = {(p["from_world"], p["to_world"]): p["count"] for p in doc["world_door_pairs"]}
            self.assertEqual(pairs[("Commonwealth", "DLC03FarHarbor")], 2)
            self.assertEqual(pairs[("DLC03FarHarbor", "Commonwealth")], 2)
            self.assertEqual(pairs[("Commonwealth", "DiamondCity")], 1)
            self.assertEqual(pairs[("DiamondCity", "Commonwealth")], 1)

            # Interior-only LCTN resolved via interior load door to DiamondCity
            loc_by_edid = {r["edid"]: r for r in doc["locations"]}
            self.assertEqual(loc_by_edid["DCInteriorOnlyLocation"]["world_edid"], "DiamondCity")
            self.assertEqual(loc_by_edid["DCInteriorOnlyLocation"]["world_resolution"], "interior_door_bfs")

    def test_sf_census_synthetic_keywords_and_core_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sf_esm, core_esm, reg_esm = self._build_sf_fixtures(os.path.join(tmp, "inputs"))
            out_json = os.path.join(tmp, "out", "sf_census.json")
            rc = slc.main(
                [
                    "--starfield",
                    sf_esm,
                    "--core",
                    core_esm,
                    "--registration",
                    reg_esm,
                    "--out",
                    out_json,
                ]
            )
            self.assertEqual(rc, 0)
            with open(out_json, encoding="utf-8") as f:
                raw_text = f.read()
            self.assertNotIn("LOADING_SCREEN_TIP_PROSE_FORBIDDEN", raw_text)
            doc = json.loads(raw_text)

            self.assertEqual(doc["counts"]["STDT"], 1)
            self.assertEqual(doc["counts"]["PNDT"], 1)
            self.assertEqual(doc["counts"]["LCTN"], 3)
            self.assertEqual(doc["counts"]["LSCR"], 1)
            self.assertEqual(doc["counts"]["WRLD"], 1)
            self.assertEqual(doc["map_markers"]["total"], 1)
            self.assertEqual(doc["lever_keywords"]["PCM_OverlayExclusionZone"]["form_id"], "0x001984BD")
            self.assertEqual(doc["lever_keywords"]["LocTypeNoPCMScanTreeContent"]["form_id"], "0x0011D575")
            self.assertEqual(doc["lctn_summary"]["ssol"]["descendants_count"], 2)

            core_wrld = doc["our_core"]["worlds"][0]
            self.assertEqual(core_wrld["edid"], "FO4Core_Commonwealth")
            self.assertEqual(core_wrld["fnam_int"], 0)
            self.assertEqual(core_wrld["biome"]["edid"], "DesertRockyNoLifeMars")

            core_loc = doc["our_core"]["locations"][0]
            self.assertEqual(core_loc["keywords"], [{"form_id": "0x002CA99D", "edid": "LocTypeOverlay"}])
            self.assertFalse(any(core_loc["exclusion_levers_present"].values()))
            self.assertEqual(doc["our_registration"]["pndt_overrides"][0]["master_worldspaces_count"], 1)

    def test_refuses_git_worktree_and_game_directory_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fo4_esm, _ = self._build_fo4_fixtures(os.path.join(tmp, "clean_inputs"))
            sf_esm, _, _ = self._build_sf_fixtures(os.path.join(tmp, "clean_sf"))

            # 1. Refuse real repo worktree path
            repo_out = os.path.join(REPO, "forbidden_census_output.json")
            with self.assertRaises(fwc.CensusPathError):
                fwc.refuse_unsafe_output_path(repo_out, [fo4_esm])
            self.assertEqual(fwc.main(["--out", repo_out, fo4_esm]), 1)
            self.assertEqual(slc.main(["--starfield", sf_esm, "--out", repo_out]), 1)
            self.assertFalse(os.path.exists(repo_out))

            # 2. Refuse synthetic Git worktree (.git file) and Git repo (.git dir)
            fake_wt = os.path.join(tmp, "fake_worktree")
            os.makedirs(os.path.join(fake_wt, "nested"), exist_ok=True)
            with open(os.path.join(fake_wt, ".git"), "w", encoding="utf-8") as f:
                f.write("gitdir: ../main/.git/worktrees/fake\n")
            wt_out = os.path.join(fake_wt, "nested", "census.json")
            with self.assertRaises(fwc.CensusPathError):
                fwc.refuse_unsafe_output_path(wt_out, [fo4_esm])

            # 3. Refuse game installation folder with Starfield.exe / Fallout4.exe
            fake_game = os.path.join(tmp, "StarfieldInstall")
            os.makedirs(os.path.join(fake_game, "sub"), exist_ok=True)
            with open(os.path.join(fake_game, "Starfield.exe"), "wb") as f:
                f.write(b"MZ")
            with self.assertRaises(fwc.CensusPathError):
                slc.refuse_unsafe_output_path(os.path.join(fake_game, "sub", "out.json"), [sf_esm])

            # 4. Refuse output inside <Game>/ or <Game>/Data/ when input comes from <Game>/Data/*.esm
            game_data = os.path.join(tmp, "Fallout4Root", "Data")
            fo4_in_game, _ = self._build_fo4_fixtures(game_data)
            for bad_out in (
                os.path.join(tmp, "Fallout4Root", "census.json"),
                os.path.join(tmp, "Fallout4Root", "Data", "census.json"),
            ):
                with self.assertRaises(fwc.CensusPathError):
                    fwc.refuse_unsafe_output_path(bad_out, [fo4_in_game])

            # 5. Refuse Steam steamapps/common/... path even before directories exist
            steam_out = os.path.join(tmp, "steamapps", "common", "Starfield", "census.json")
            with self.assertRaises(fwc.CensusPathError):
                slc.refuse_unsafe_output_path(steam_out, [sf_esm])

            # 6. Refuse aliasing input plugin path
            with self.assertRaises(fwc.CensusPathError):
                fwc.refuse_unsafe_output_path(fo4_esm, [fo4_esm])


if __name__ == "__main__":
    unittest.main()
