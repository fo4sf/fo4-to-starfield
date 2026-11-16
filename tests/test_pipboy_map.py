"""Offline unit tests for Pip-Boy MAP slices 1-4 (pipboy_map.{h,cpp}, pipboy_map_store.py, FO4SF_PipboyTravel.psc,
and docs/ui/pipboy-map-s1-s4.md)."""
import os
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts" / "ui") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "ui"))

from fo4sf.planet.esm import ESM, PERSISTENT, Plugin, PluginWriter, Record, group_bytes, zbytes  # noqa: E402
import make_pipboy_probe as mpp  # noqa: E402
import make_probe_swf as swf  # noqa: E402
import pipboy_map_store as store  # noqa: E402
import pipboy_probe_install as pbi  # noqa: E402
import swf_names  # noqa: E402


class CoordinateAndBitsetTests(unittest.TestCase):
    def test_vault111_and_commonwealth_round_trip(self):
        # Vault 111 canonical FO4 (-89271.7, 91369.6) <-> merged Starfield (-2475.31, -1394.72)
        sf_x, sf_y = store.fo4_to_sf_merged(-89271.7, 91369.6)
        self.assertAlmostEqual(sf_x, -2475.31, places=2)
        self.assertAlmostEqual(sf_y, -1394.72, places=2)
        fo4_x, fo4_y = store.sf_merged_to_fo4(sf_x, sf_y)
        self.assertAlmostEqual(fo4_x, -89271.7, places=3)
        self.assertAlmostEqual(fo4_y, 91369.6, places=3)

    def test_diamond_city_child_world_projection(self):
        cx, cy = store.project_child_world(1000.0, 2000.0, store.DIAMOND_CITY_WRLD)
        self.assertAlmostEqual(cx, 1000.0 - 16384.0, places=3)
        self.assertAlmostEqual(cy, 2000.0 - 27852.80078125, places=3)

    def test_landmark_pixel_projections_land_inside_usable_gutter_box(self):
        # Sanctuary (-80768.19, 88174.80) -> ~(469.5, 194.6); The Castle (48321.93, -46600.11) -> ~(1453.1, 1221.5)
        sx, sy = store.world_to_map_pixel(-80768.19, 88174.80)
        cx, cy = store.world_to_map_pixel(48321.93, -46600.11)
        self.assertAlmostEqual(sx, 469.5, delta=0.5)
        self.assertAlmostEqual(sy, 194.6, delta=0.5)
        self.assertAlmostEqual(cx, 1453.1, delta=0.5)
        self.assertAlmostEqual(cy, 1221.5, delta=0.5)

    def test_24bit_discovery_globals_round_trip_through_ieee754_float32(self):
        flags = [(i % 3 == 0 or i in (0, 23, 24, 314)) for i in range(315)]
        packed = store.pack_discovery_bits(flags)
        self.assertEqual(len(packed), 14)
        # Simulate exact C++ TESGlobal float32 storage at +0x48
        as_f32 = [struct.unpack("<f", struct.pack("<f", float(v)))[0] for v in packed]
        unpacked = store.unpack_discovery_bits(as_f32, 315)
        self.assertEqual(unpacked, flags)
        # All 24 bits set (0xFFFFFF = 16,777,215) must survive float32 without rounding
        max24 = (1 << 24) - 1
        rt = int(struct.unpack("<f", struct.pack("<f", float(max24)))[0])
        self.assertEqual(rt, max24)
        with self.assertRaises(store.MapStoreError):
            store.pack_discovery_bits([True], bits_per_global=25)


class WorldMapSwfAndPatcherTests(unittest.TestCase):
    def test_bc1_dds_to_worldmap_swf_passes_probe_installer(self):
        # 4 blocks (8x8): pure red (0xF800) and pure blue (0x001F)
        blocks = struct.pack("<HHI", 0xF800, 0x001F, 0x00000000) * 4
        dds = b"DDS " + struct.pack("<IIII", 124, 0x1007, 8, 8) + bytes(64) + b"DXT1" + bytes(40) + blocks
        w, h, argb = store.parse_dds_bc1(dds)
        self.assertEqual((w, h), (8, 8))
        self.assertEqual(tuple(argb[:4]), (255, 255, 0, 0))
        data = store.worldmap_swf_bytes(argb, w, h)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "FO4SF_WorldMap.swf")
            Path(out).write_bytes(data)
            self.assertIsNone(pbi.swf_problem(out))
            info = swf.read_movie_header(data) if hasattr(swf, "read_movie_header") else None
            if info is not None:
                self.assertEqual(info["version"], 12)
            # Verify frame rect equals (0, 8*20, 0, 8*20)
            body = zlib.decompress(data[8:])
            r = swf.BitReader(body, 0)
            self.assertEqual(swf.read_rect(r), (0, 160, 0, 160))

    def test_dx10_bc1_header_supported(self):
        blocks = struct.pack("<HHI", 0x07E0, 0x0000, 0x00000000)
        dx10 = struct.pack("<IIIII", 71, 3, 0, 1, 0)
        dds = b"DDS " + struct.pack("<IIII", 124, 0x1007, 4, 4) + bytes(64) + b"DX10" + bytes(40) + dx10 + blocks
        w, h, argb = store.parse_dds_bc1(dds)
        self.assertEqual((w, h), (4, 4))
        self.assertEqual(tuple(argb[:4]), (255, 0, 255, 0))

    def test_doabc_patcher_rewrites_urls_and_preserves_abc_structure(self):
        # Construct valid minimal ABC with constant pool + 0 methods/metadata/classes/scripts/bodies
        strings = [b"WorldMapHolder", store.WORLDMAP_URL_ORIG.encode("utf-8"), store.MSGBOX_URL_ORIG.encode("utf-8")]
        abc = bytearray(struct.pack("<HH", 16, 46))
        abc += b"\x00\x00\x00"  # ints, uints, doubles
        abc += store._pack_u30(len(strings) + 1)
        for s in strings:
            abc += store._pack_u30(len(s)) + s
        abc += b"\x00\x00\x00"  # namespaces, ns_sets, multinames
        abc += b"\x00\x00\x00\x00\x00"  # methods, metadata, classes, scripts, bodies
        doabc = struct.pack("<I", 1) + b"Pipboy_MapPage\x00" + bytes(abc)
        body = (
            swf.rect(0, 876 * 20, 0, 700 * 20)
            + struct.pack("<HH", 30 << 8, 1)
            + swf.tag(swf.FILE_ATTRIBUTES, struct.pack("<I", swf.AS3))
            + swf.tag(store.DO_ABC, doabc)
            + swf.tag(swf.SHOW_FRAME)
            + swf.tag(swf.END)
        )
        raw_swf = b"CWS" + bytes([12]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body)
        patched, counts = store.patch_map_page_swf(raw_swf)
        self.assertEqual(counts, {store.WORLDMAP_URL_ORIG: 1, store.MSGBOX_URL_ORIG: 1})
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "Pipboy_MapPage.swf")
            Path(p).write_bytes(patched)
            self.assertIsNone(pbi.swf_problem(p))
        # Parse patched DoABC with swf_names.Abc to verify constant pool integrity
        decomp = zlib.decompress(patched[8:])
        nul = decomp.index(b"Pipboy_MapPage\x00") + len(b"Pipboy_MapPage\x00")
        parsed_abc = swf_names.Abc(decomp[nul:-4])  # exclude ShowFrame (2B) + End (2B)
        self.assertEqual(
            parsed_abc.strings,
            ["", "WorldMapHolder", store.WORLDMAP_URL_PATCHED, store.MSGBOX_URL_PATCHED],
        )

    def test_component_paths_accepted_by_pipboy_probe_install_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            mpp.stage(tmp)
            iface = Path(tmp) / "Data" / "Interface"
            stub = (iface / "FO4SF_PipboyMenu.swf").read_bytes()
            (iface / "FO4SF_Fo4Shell.swf").write_bytes(stub)
            (iface / "Pipboy_MapPage.swf").write_bytes(stub)
            comp_dir = iface / "Components"
            comp_dir.mkdir(parents=True, exist_ok=True)
            (comp_dir / "FO4SF_WorldMap.swf").write_bytes(stub)
            (comp_dir / "PipboyMessageBox.swf").write_bytes(stub)
            problems = pbi.stage_problems(
                tmp,
                extra_movie="FO4SF_Fo4Shell",
                pages=["Pipboy_MapPage"],
                components=["Components/FO4SF_WorldMap", "Components/PipboyMessageBox"],
            )
            self.assertEqual(problems, [])


class TravelPluginAndStoreTests(unittest.TestCase):
    def test_travel_plugin_writes_valid_esm_with_22_globals(self):
        with tempfile.TemporaryDirectory() as tmp:
            esm_path = os.path.join(tmp, store.TRAVEL_PLUGIN)
            store.write_travel_plugin(esm_path, survival=True, initial_disc_bits=[0b10101, 0xFFFFFF])
            with Plugin(esm_path) as p:
                self.assertTrue(p.flags & 0x01)
                self.assertEqual(p.masters, ["Starfield.esm"])
                globs = list(p.records("GLOB"))
                self.assertEqual(len(globs), 8 + store.DISC_GLOBAL_COUNT)
                by_edid = {g.edid: struct.unpack("<f", g.get(b"FLTV"))[0] for g in globs}
                self.assertEqual(by_edid["FO4SF_SurvivalMode"], 1.0)
                self.assertEqual(int(by_edid["FO4SF_MapDisc00"]), 0b10101)
                self.assertEqual(int(by_edid["FO4SF_MapDisc01"]), 0xFFFFFF)

    def test_store_tsv_round_trip(self):
        sample = [
            {
                "index": 0,
                "plugin_code": 1,
                "local_id": 0x0A7759,
                "type": 15,
                "init_disc": True,
                "x_fo4": -89271.7,
                "y_fo4": 91369.6,
                "arr_x_sf": -2445.446,
                "arr_y_sf": -1400.664,
                "arr_z_sf": 115.969,
                "arr_h_deg": 274.45,
                "label": "MARKER_000",
            }
        ]
        tsv = store.format_store_tsv(sample)
        back = store.parse_store_tsv(tsv)
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0]["local_id"], 0x0A7759)
        self.assertTrue(back[0]["init_disc"])
        self.assertAlmostEqual(back[0]["arr_x_sf"], -2445.446, places=3)

    def _synthetic_marker_plugin(self, path, masters, markers, wrld_id=0x01000800, cell_id=0x01000801):
        w = PluginWriter(masters, flags=ESM)
        refr_bytes = b"".join(
            Record(
                b"REFR",
                fid,
                [
                    (b"EDID", zbytes(edid)),
                    (b"NAME", struct.pack("<I", 0x00000010)),
                    (b"XMRK", b""),
                    (b"FNAM", struct.pack("<I", fnam)),
                    (b"FULL", zbytes(label)),
                    (b"TNAM", struct.pack("<H", sf_tnam)),
                    (b"DATA", struct.pack("<6f", x_m, y_m, z_m, 0.0, 0.0, 0.0)),
                ],
                flags=PERSISTENT,
            ).to_bytes(compress=False)
            for fid, edid, label, sf_tnam, fnam, x_m, y_m, z_m in markers
        )
        cell_rec = Record(b"CELL", cell_id, [(b"EDID", zbytes("TestPersistentCell"))]).to_bytes(compress=False)
        cell_children = group_bytes(struct.pack("<I", cell_id), group_bytes(struct.pack("<I", cell_id), refr_bytes, gtype=8), gtype=6)
        wrld_rec = Record(b"WRLD", wrld_id, [(b"EDID", zbytes("FO4Core_Commonwealth"))]).to_bytes(compress=False)
        wrld_children = group_bytes(struct.pack("<I", wrld_id), cell_rec + cell_children, gtype=1)
        top_wrld = group_bytes("WRLD", wrld_rec + wrld_children, gtype=0)
        head = Record(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 0.96, 4, 0x950))] + [(b"MAST", zbytes(m)) for m in masters], ESM, 0, 576, 0)
        Path(path).write_bytes(head.to_bytes(compress=False) + top_wrld)

    def test_build_store_cli_extracts_core_and_mapmarkers_plugins_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            core_esm = os.path.join(tmp, "FO4TerrainCore.esm")
            mm_esm = os.path.join(tmp, "FO4SFMapMarkers.esm")
            tsv_out = os.path.join(tmp, "FO4SFPipboyMapMarkers.tsv")
            travel_out = os.path.join(tmp, store.TRAVEL_PLUGIN)
            # Core has 2 markers (self_index=1 -> 0x01......), unlifted Z=100.0
            self._synthetic_marker_plugin(
                core_esm,
                ["Starfield.esm"],
                [
                    (0x010A7759, "FO4Core_CommonwealthMapMarker", "SITE_STATION", 86, 0x1B, -991.13, 1144.97, 100.0),
                    (0x010A775B, "FO4Core_CommonwealthMapMarkerVault111", "SITE_VAULT", 86, 0x1B, -1275.31, 1305.28, 127.2),
                ],
            )
            # FO4SFMapMarkers overrides those 2 with lifted Z (+2.5) and adds 1 own extra marker (0x02000900) + 1 landing (0x020008F2)
            self._synthetic_marker_plugin(
                mm_esm,
                ["Starfield.esm", "FO4TerrainCore.esm"],
                [
                    (0x010A7759, "FO4Core_CommonwealthMapMarker", "SITE_STATION", 86, 0x13, -991.13, 1144.97, 102.5),
                    (0x010A775B, "FO4Core_CommonwealthMapMarkerVault111", "SITE_VAULT", 86, 0x33, -1275.31, 1305.28, 129.7),
                    (0x020008F2, "FO4SF_LandingMarker", "SITE_LANDING", 45, 0x33, -950.0, 1100.0, 105.0),
                    (0x02000900, "FO4Core_CommonwealthMapMarkerM019C6F", "SITE_EXTRA", 22, 0x03, 500.0, -300.0, 25.0),
                ],
            )
            rc = store.main(["build-store", "--core", core_esm, "--markers-esm", mm_esm, "--out", tsv_out])
            self.assertEqual(rc, 0)
            rows = store.parse_store_tsv(Path(tsv_out).read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 3, "landing marker 0x8F2 excluded by default")
            self.assertEqual([r["plugin_code"] for r in rows], [1, 1, 0])
            self.assertEqual([r["local_id"] for r in rows], [0x0A7759, 0x0A775B, 0x000900])
            # Location icon types stay < 85 (never 85 PlayerSetMarker or 86 PlayerLocMarker)
            self.assertEqual(rows[0]["type"], 27)  # Filling Station
            self.assertEqual(rows[1]["type"], 15)  # Vault
            self.assertEqual(rows[2]["type"], 7)   # Military Base (sf_type 22 -> fo4_id 7)
            # Only SITE_VAULT had FNAM 0x20 bit set (0x33 & 0x20 != 0)
            self.assertEqual([r["init_disc"] for r in rows], [False, True, False])
            self.assertAlmostEqual(rows[1]["arr_x_sf"], -2475.31, places=2)
            self.assertAlmostEqual(rows[1]["arr_y_sf"], -1394.72, places=2)
            self.assertAlmostEqual(rows[1]["arr_z_sf"], 129.7, places=2)
            # stage-travel-esm --store seeds FO4SF_MapDisc00 from init_disc so C++ and Papyrus agree on frame 0
            self.assertEqual(store.main(["stage-travel-esm", "--store", tsv_out, "--out", travel_out]), 0)
            with Plugin(travel_out) as tp:
                by_edid = {g.edid: int(struct.unpack("<f", g.get(b"FLTV"))[0]) for g in tp.records("GLOB")}
                self.assertEqual(by_edid["FO4SF_MapDisc00"], 0b010)


class SourceAndContractTests(unittest.TestCase):
    cpp = (PLUGIN / "src" / "pipboy_map.cpp").read_text(encoding="utf-8")
    hdr = (PLUGIN / "src" / "pipboy_map.h").read_text(encoding="utf-8")
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
    psc = (ROOT / "scripts" / "mapmarkers" / "FO4SF_PipboyTravel.psc").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "ui" / "pipboy-map-s1-s4.md").read_text(encoding="utf-8")

    def test_shipped_off_and_ini_defaults_present(self):
        for line in (
            "Map=0",
            "MapKey=0x4D",
            "MapPage=3",
            "MapMenus=GalaxyStarMapMenu",
            "MapBlockStarMap=1",
            "MapStore=FO4SFPipboyMapMarkers.tsv",
            "MapTravelPlugin=FO4SFPipboyTravel.esm",
            "MapTravelScript=FO4SF_PipboyTravel.Go",
            "MapSurvival=0",
            "MapHeadingAt=",
            "MapGlobalValueAt=0",
            "MapGameHourId=0x38",
            "MapGameDaysPassedId=0x39",
            "MapFileCollectionAt=0x1580",
            "MapExtraListAt=0xC8",
            "MapMarkerFlagsAt=0x18",
            "MapMarkerDiscoveredMask=0x20",
        ):
            self.assertRegex(self.ini, rf"\n{re.escape(line)}\r?\n", line)
        self.assertTrue(self.ini.isascii(), "FO4SFPipboyMenu.ini must stay pure ASCII")
        self.assertIn('if (ReadIniNumber(a_ini, L"Map", 0) == 0) {\n\t\t\treturn;\n\t\t}', self.cpp)

    def test_m_key_swallow_no_reopen_loop_and_complete_starmap_block(self):
        # Suppression must NEVER reopen FO4SF_PipboyMenu (fixes close-then-reopen loop)
        sup = self.cpp[self.cpp.index("bool SuppressVanillaMapMenus()"):self.cpp.index("void HandleClosedMapKeyMainThread")]
        self.assertNotIn("kShow", sup)
        self.assertNotIn("OurMenuFixed()", sup)
        # Complete star-map lockout in UI::menuMap + BSInputEventUser swallow while open
        self.assertIn("entry.value.initFunc = &BlockedStarMapCreate;", self.cpp)
        self.assertIn("step=starmap_blocked", self.cpp)
        self.assertIn("RE::InputEvent::Status::kStop", self.cpp)
        self.assertIn("PipboyMap::ShouldHandleInput(a_event)", self.main)
        self.assertIn("PipboyMap::OnButtonInput(a_event)", self.main)
        self.assertIn("g_stage >= 4 || PipboyMap::Enabled()", self.main)

    def test_live_engine_discovery_and_papyrus_agreement(self):
        # C++ reads live ExtraMapMarker kDiscovered (0x20 via REL::ID 44761) and syncs into FO4SF_MapDisc00..13;
        # Papyrus checks IsBitDiscovered(storeIdx) (not CanFastTravelToMarker/IsMapMarkerVisible which are 1 on FNAM 0x03)
        self.assertIn("ExtraDataList.GetExtraMapMarker", self.cpp)
        self.assertIn("step=map_disc_sync", self.cpp)
        self.assertIn("EnsureGlobalValueOffset(", self.cpp)
        self.assertIn('IsType(file, "TESFile@@")', self.cpp)
        self.assertIn("bool canTravel = IsBitDiscovered(storeIdx)", self.psc)
        self.assertNotIn("CanFastTravelToMarker()", self.psc)
        self.assertNotIn("IsMapMarkerVisible()", self.psc)

    def test_cpp_uses_only_checked_gfx_methods_and_checks_slot_0x2e(self):
        # SetArraySize / PushBack / SetElement would trigger unchecked REL::ID lookups; AS3 Array uses length + push
        for forbidden in (".SetArraySize(", ".PushBack(", ".SetElement(", ".RemoveElements("):
            self.assertNotIn(forbidden, self.cpp, forbidden)
        self.assertIn('markersArr.SetMember("length"', self.cpp)
        self.assertIn('a_arr.Invoke("push"', self.cpp)
        self.assertIn('dataObj.SetMember("RemoveAllMapMarkers", RE::Scaleform::GFx::Value(true))', self.cpp)
        self.assertIn("kCreateObjectSlot = 0x2E;", self.cpp)
        self.assertIn("!InImage(slot[kCreateObjectSlot], 1)", self.cpp)
        self.assertIn('a_name == "CheckHardcoreModeFastTravel"', self.cpp)
        self.assertIn('a_name == "RefreshMapMarkers"', self.cpp)

    def test_papyrus_contract_no_sf_reserved_keywords(self):
        # Starfield Papyrus reserves Guard and ProtectsFunctionLogic case-insensitively
        tokens = {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", self.psc)}
        self.assertNotIn("guard", tokens)
        self.assertNotIn("protectsfunctionlogic", tokens)
        self.assertIn("Function Go() global", self.psc)
        self.assertIn("Game.FastTravel(dest)", self.psc)
        self.assertIn("elseif tripMetres > 1.0 && (gDays == None || (gDays.GetValue() - daysBefore) < 0.001)", self.psc)
        # TeleportFollowers must run after both native FastTravel and fallback MoveTo
        self.assertGreater(self.psc.index("SQ_FollowersScript.GetScript()"), self.psc.index("Game.FadeOutGame(False"))

    def test_doc_has_four_pc_cards_and_s1c3_gate(self):
        self.assertIn("S1-c3", self.doc)
        self.assertIn("markers=309", self.doc)
        self.assertNotIn("markers=310", self.doc)
        for slice_num in (1, 2, 3, 4):
            self.assertIn(f"PC Card — Slice {slice_num}:", self.doc)
        self.assertIn("slot_0x2e_in_image=1", self.cpp)
        self.assertIn("does NOT prove that slot 0x2E is", self.cpp)
        self.assertIn("Slices 1–2 (`MapKey` + Star-Map Block + World Texture) are testable first", self.doc)
        self.assertIn("Do NOT claim Slices 3–4 are verified", self.doc)
        self.assertIn("does **not** prove that slot `0x2E` is `CreateObject`", self.doc)


if __name__ == "__main__":
    unittest.main()
