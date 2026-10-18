"""Synthetic tests for core64n navmesh.convert driver. No game data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "actors"))
sys.path.insert(0, str(ROOT / "src"))
import navmesh_core64n_convert as conv  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402
import test_navmesh as tn  # noqa: E402


class Core64nConvertTests(unittest.TestCase):
    def test_parse_overflow_fid(self):
        msg = "piece (17000, (2, -4)): 40000 triangles / 12 vertices exceed i16 indices"
        self.assertEqual(conv.parse_overflow_fid(msg), 17000)
        self.assertIsNone(conv.parse_overflow_fid("vertices leave cell"))

    def test_convert_with_refusals_keeps_cell_line_pairs(self):
        nav = (0x100, nm.parse(tn.fo4_bytes(0x3C, (0, 0), *tn.square(-700, 100, 700, 800, 70.0))))
        pieces, report, refused = conv.convert_with_refusals([nav])
        self.assertEqual(refused, [])
        self.assertEqual(sorted(p.cell for p in pieces), [(-1, 0), (0, 0)])
        self.assertEqual(report["links"]["cell_line"], 2)
        stats = conv.cell_stats_from_pieces(pieces)
        self.assertEqual(stats["-1,0"]["navm"], 1)
        self.assertEqual(stats["0,0"]["navm"], 1)
        self.assertEqual(stats["-1,0"]["cell_line_links"], 2)
        self.assertEqual(stats["0,0"]["cell_line_links"], 2)
        self.assertEqual(stats["-1,0"]["fo4_portal_links"], 0)

    def test_convert_with_refusals_drops_overflow_ids_and_retries(self):
        good = (0x111, nm.parse(tn.fo4_bytes(0x3C, (0, 0), *tn.square(0, 0, 700, 700))))
        bad = (0x222, nm.parse(tn.fo4_bytes(0x3C, (0, 0), *tn.square(1400, 0, 2100, 700))))
        calls = {"n": 0}
        real = conv.nm.convert

        def fake_convert(fo4, door_refs=None):
            calls["n"] += 1
            if any(fid == 0x222 for fid, _ in fo4):
                raise nm.NavmeshError("piece (546, (1, 0)): 40000 triangles / 8 vertices exceed i16 indices")
            return real(fo4, door_refs=door_refs)

        with patch.object(conv.nm, "convert", fake_convert):
            pieces, report, refused = conv.convert_with_refusals([good, bad])
        self.assertEqual(calls["n"], 2)
        self.assertEqual([row["id"] for row in refused], ["00000222"])
        self.assertEqual(refused[0]["reason"], "i16_index_overflow")
        self.assertEqual(report["fo4_navmeshes"], 1)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0].src, 0x111)

    def test_door_sources_from_list_bases(self):
        objects = {
            "bases": [{"edid": "stat"}, {"edid": "door", "door": {"origin_offset": [0, 0, 0]}}],
            "refs": [
                {"src": "0000AA:Fallout4.esm", "base": 0},
                {"src": "0000BB:Fallout4.esm", "base": 1},
            ],
        }
        self.assertEqual(conv.door_sources_from_objects(objects), {0xBB: "0000BB:Fallout4.esm"})

    def test_overlay_stats_drops_rim_cells(self):
        raw = {
            "-33,0": {"navm": 1, "triangles": 4, "vertices": 4, "area": 1.0,
                      "cell_line_links": 0, "fo4_portal_links": 0},
            "-10,11": {"navm": 2, "triangles": 10, "vertices": 8, "area": 3.0,
                       "cell_line_links": 2, "fo4_portal_links": 1},
        }
        over = conv.overlay_stats(raw)
        self.assertEqual(list(over), ["-10,11"])

    def test_compare_to_inventory_clip_increase_is_not_lost(self):
        fo4 = {"-10,11": {"triangles": 100, "area": 50.0}, "2,-4": {"triangles": 20, "area": 8.0}}
        converted = {
            "-10,11": {"navm": 3, "triangles": 110, "vertices": 80, "area": 50.0,
                       "cell_line_links": 4, "fo4_portal_links": 2},
        }
        cmp = conv.compare_to_inventory(fo4, converted)
        self.assertEqual(cmp["inventory"]["lost"], 1)
        self.assertEqual(cmp["inventory"]["total_fo4_triangles"], 120)
        self.assertEqual(cmp["inventory"]["total_sf_triangles"], 110)
        self.assertEqual(cmp["named_cells"]["-10,11"]["navm"], 3)
        self.assertEqual(cmp["named_cells"]["2,-4"]["triangles"], 0)
        self.assertEqual(cmp["named_cells"]["2,-4"]["fo4_triangles"], 20)
        self.assertEqual(cmp["densest_converted"][0]["cell"], "-10,11")

    def test_write_export_matches_nm_export_and_refuses_overwrite(self):
        nav = (0x100, nm.parse(tn.fo4_bytes(0x3C, (0, 0), *tn.square(-700, 100, 700, 800, 70.0))))
        pieces, _report, _refused = conv.convert_with_refusals([nav])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "navmesh.json"
            conv.write_export(path, pieces)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, nm.export(pieces))
            with self.assertRaises(FileExistsError):
                conv.write_export(path, pieces)

    def test_piece_area_is_xy_not_3d(self):
        pc = nm.Piece(1, (0, 0))
        pc.pos = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 3.0, 10.0)]
        pc.tris = [(0, 1, 2)]
        self.assertAlmostEqual(conv.piece_area(pc), 6.0, places=6)

    def test_committed_core64n_report_matches_inventory_window(self):
        data = ROOT / "docs" / "actors" / "data"
        report = json.loads((data / "core64n-convert-report.json").read_text(encoding="utf-8"))
        fo4 = json.loads((data / "core64c-fo4-navmesh.json").read_text(encoding="utf-8"))
        self.assertEqual(report["fo4"]["parsed"], 7047)
        self.assertEqual(report["refused_ids"], [])
        self.assertEqual(report["convert"]["fo4_triangles"], 3439338)
        self.assertEqual(report["convert"]["pieces"], 12104)
        self.assertEqual(report["convert"]["triangles"], 3749066)
        self.assertEqual(report["links"], {"cell_line": 156549, "fo4_portal": 134876})
        self.assertEqual(report["pieces"]["overlay_cells"], len(fo4))
        self.assertEqual(report["inventory_comparison"]["inventory"]["lost"], 0)
        self.assertEqual(report["red_rocket_smoke"]["pieces"], 156)
        self.assertEqual(len(report["export_bands"]), 11)

    def test_list_export_bands_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "band_5_14.json").write_text("{}", encoding="utf-8")
            (tmp / "band_-55_-46.json").write_text("{}", encoding="utf-8")
            (tmp / "notes.txt").write_text("no", encoding="utf-8")
            bands = conv.list_export_bands(tmp)
            self.assertEqual([b["name"] for b in bands], ["band_-55_-46.json", "band_5_14.json"])
            self.assertTrue(all(b["size"] >= 2 for b in bands))


if __name__ == "__main__":
    unittest.main()
