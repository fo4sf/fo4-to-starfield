"""Offline tests for Round 10 Slice W5: A4 console-free walking headings & R8 stand-in truth labels."""
from __future__ import annotations

import json
import math
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
NEWGAME_DIR = REPO_ROOT / "scripts" / "newgame"
SRC_DIR = REPO_ROOT / "src"
for _p in (str(NEWGAME_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import walk_headings as wh  # noqa: E402
from fo4sf.planet.esm import ESM, HEADER_FORM_VERSION, HEDR_VERSION, Record, group_bytes, zbytes  # noqa: E402

WALK_SCRIPT = NEWGAME_DIR / "walk_headings.py"
WALK_DOC = REPO_ROOT / "docs" / "testing" / "console-free-walk-list.md"
QUEST_DOCS = {
    "a3": REPO_ROOT / "docs" / "quests" / "first-missions-places.md",
    "a4": REPO_ROOT / "docs" / "quests" / "next-story-missions-a4.md",
    "a7": REPO_ROOT / "docs" / "quests" / "next-story-missions-a7.md",
    "a7b": REPO_ROOT / "docs" / "quests" / "next-story-missions-a7b.md",
    "a7d": REPO_ROOT / "docs" / "quests" / "next-story-missions-a7d.md",
}

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = (
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
)


def _write_synthetic_ref_esm(path: Path, group: str, refs: list[tuple[bytes, int, tuple[float, float, float]]]) -> None:
    """Create a minimal valid TES4 plugin containing REFR/ACHR records with DATA positions."""
    cell_rec = Record(b"CELL", 0x01001805, [(b"EDID", zbytes("SyntheticCell"))])
    child_stream = bytearray()
    for sig, fid, pos in refs:
        data = struct.pack("<6f", pos[0], pos[1], pos[2], 0.0, 0.0, 0.0)
        child_stream += Record(sig, fid, [(b"DATA", data)]).to_bytes(compress=False)
    cell_children = group_bytes(struct.pack("<I", 0x01001805), bytes(child_stream), gtype=6)
    top = group_bytes(group, cell_rec.to_bytes(compress=False) + cell_children, gtype=0)
    hsubs = [
        (b"HEDR", struct.pack("<fII", HEDR_VERSION, len(refs) + 2, 0x001000)),
        (b"MAST", zbytes("Starfield.esm")),
    ]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top)


def _write_synthetic_commonwealth_navm_esm(
    path: Path,
    quad_merged: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> None:
    """Build a minimal Fallout4-style TES4 plugin with WRLD 0x0000003C and a 2-triangle v15 NAVM quad."""
    fo4_verts = [
        ((p[0] - wh.MERGE_OFFSET_X) / wh.FO4_TO_SF_SCALE, (p[1] - wh.MERGE_OFFSET_Y) / wh.FO4_TO_SF_SCALE, p[2] / wh.FO4_TO_SF_SCALE)
        for p in quad_merged
    ]
    nvnm = bytearray(struct.pack("<5I", 15, 0xA5E9A03C, 0x0000003C, 0, len(fo4_verts)))
    for v in fo4_verts:
        nvnm += struct.pack("<3f", *v)
    nvnm += struct.pack("<I", 2)
    # 21-byte FO4 v15 triangle stride: 3H verts + 3H edges + f32 height + 5 bytes flags
    nvnm += struct.pack("<6Hf5B", 0, 1, 2, 0xFFFF, 1, 0xFFFF, 0.0, 0, 0, 0, 0, 0)
    nvnm += struct.pack("<6Hf5B", 0, 2, 3, 0, 0xFFFF, 0xFFFF, 0.0, 0, 0, 0, 0, 0)

    wrld_rec = Record(b"WRLD", 0x0000003C, [(b"EDID", zbytes("Commonwealth"))])
    navm_rec = Record(b"NAVM", 0x00090001, [(b"NVNM", bytes(nvnm))])
    wrld_children = group_bytes(struct.pack("<I", 0x0000003C), navm_rec.to_bytes(compress=False), gtype=1)
    top = group_bytes("WRLD", wrld_rec.to_bytes(compress=False) + wrld_children, gtype=0)
    hsubs = [(b"HEDR", struct.pack("<fII", HEDR_VERSION, 3, 0x001000))]
    tes4 = Record(b"TES4", 0, hsubs, ESM, 0, HEADER_FORM_VERSION, 0)
    path.write_bytes(tes4.to_bytes(compress=False) + top)


class WalkHeadingsAndTruthLabelsTests(unittest.TestCase):
    def test_starfield_compass_heading_convention_matches_core_walk_script(self) -> None:
        origin = (0.0, 0.0, 0.0)
        # Verified against FO4SF_CoreCandidateWalk.psc:229-233 (fwdX=sin, fwdY=cos)
        self.assertAlmostEqual(wh.compass_heading_deg(origin, (0.0, 10.0, 0.0)), 0.0, places=4)
        self.assertAlmostEqual(wh.compass_heading_deg(origin, (10.0, 0.0, 0.0)), 90.0, places=4)
        self.assertAlmostEqual(wh.compass_heading_deg(origin, (0.0, -10.0, 0.0)), 180.0, places=4)
        self.assertAlmostEqual(wh.compass_heading_deg(origin, (-10.0, 0.0, 0.0)), 270.0, places=4)
        self.assertAlmostEqual(wh.compass_heading_rad(origin, (10.0, 0.0, 0.0)), math.pi / 2.0, places=4)
        self.assertEqual(wh.compass_cardinal(0.0), "N")
        self.assertEqual(wh.compass_cardinal(90.0), "E")
        self.assertEqual(wh.compass_cardinal(180.0), "S")
        self.assertEqual(wh.compass_cardinal(270.0), "W")

    def test_opening_route_continuity_legs_and_safe_standoffs(self) -> None:
        cont = wh.check_route_continuity()
        self.assertTrue(cont["pass"], cont["issues"])
        self.assertEqual(cont["segment_count"], 34)
        self.assertEqual(set(cont["leg_totals_m"].keys()), {"L1", "L2", "L3", "L4", "L5"})

        rows = wh.compute_route_rows()
        by_id = {r["seg_id"]: r for r in rows}

        # Leg 1 starts at exact 2f Vault 111 Cryo Pod pose and reaches Pip-Boy pickup within first-person E reach (< 1.8 m)
        self.assertEqual(by_id["1a"]["start"], [9.143, -6.614, -0.852])
        self.assertEqual(by_id["1a"]["start_yaw_deg"], 0.0)
        self.assertLess(by_id["1g"]["aim_distance_m"], 1.8)
        self.assertIn("0200126E", by_id["1b"]["action_at_target"])
        self.assertIn("02001234", by_id["1c"]["action_at_target"])

        # Leg 3 reaches exact Exit Lift Platform center (within PlatformRadius=2.0 m) via north stair landing
        self.assertEqual(by_id["3f"]["target"], [-77.742, -3.958, -1.751])
        self.assertEqual(by_id["3d"]["heading_deg"], 0.0)

        # Legs 4 & 5 stop at C6-safe ~2.83 m standoff from Codsworth (09000811) and Preston (09000802)
        self.assertGreaterEqual(by_id["4i"]["aim_distance_m"], 2.0)
        self.assertLessEqual(by_id["4i"]["aim_distance_m"], 3.5)
        self.assertGreaterEqual(by_id["5k"]["aim_distance_m"], 2.0)
        self.assertLessEqual(by_id["5k"]["aim_distance_m"], 3.5)

        # Negative continuity mutation must fail
        broken = list(wh.OPENING_WALK_SEGMENTS)
        s0 = broken[0]
        broken[0] = wh.WalkSegment(
            s0.leg_id, s0.seg_id, s0.zone, s0.label, s0.start, (99.0, 99.0, 0.0),
            s0.start_yaw_deg, s0.action_at_target, s0.anchor_ref,
        )
        bad_cont = wh.check_route_continuity(broken)
        self.assertFalse(bad_cont["pass"])
        self.assertTrue(any("gap" in msg for msg in bad_cont["issues"]))

    def test_synthetic_binary_esm_verifier_passes_and_catches_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ng_esm = tmp / "FO4SFNewGame.esm"
            ms_esm = tmp / "FO4SFMission.esm"
            cr_esm = tmp / "FO4TerrainCore.esm"

            _write_synthetic_ref_esm(ng_esm, "CELL", [
                (b"REFR", 0x0300080F, wh.BINARY_ANCHORS["v111_pipboy_pickup"]["pos"]),
                (b"REFR", 0x03000819, wh.BINARY_ANCHORS["v111_geardoor_console"]["pos"]),
            ])
            c_pos = wh.BINARY_ANCHORS["sanctuary_codsworth"]["pos"]
            p_pos = wh.BINARY_ANCHORS["concord_preston_museum_door"]["pos"]
            _write_synthetic_ref_esm(ms_esm, "WRLD", [
                (b"ACHR", 0x03000811, (c_pos[0] - wh.MERGE_OFFSET_X, c_pos[1] - wh.MERGE_OFFSET_Y, c_pos[2])),
                (b"ACHR", 0x03000802, (p_pos[0] - wh.MERGE_OFFSET_X, p_pos[1] - wh.MERGE_OFFSET_Y, p_pos[2])),
            ])
            fb = wh.BINARY_ANCHORS["v111_creek_footbridge"]["pos"]
            nb = wh.BINARY_ANCHORS["sanctuary_north_bridge"]["pos"]
            cm = wh.BINARY_ANCHORS["concord_map_marker"]["pos"]
            _write_synthetic_ref_esm(cr_esm, "WRLD", [
                (b"REFR", 0x01014BA7, (fb[0] - wh.MERGE_OFFSET_X, fb[1] - wh.MERGE_OFFSET_Y, fb[2])),
                (b"REFR", 0x01005199, (nb[0] - wh.MERGE_OFFSET_X, nb[1] - wh.MERGE_OFFSET_Y, nb[2])),
                (b"REFR", 0x010A775C, (cm[0] - wh.MERGE_OFFSET_X, cm[1] - wh.MERGE_OFFSET_Y, cm[2])),
            ])

            res = wh.verify_against_staged_esms(newgame_esm=ng_esm, mission_esm=ms_esm, core_esm=cr_esm)
            self.assertTrue(res["pass"], res["issues"])
            self.assertEqual(len(res["checked_anchors"]), 7)

            # Negative mutation: shift Pip-Boy by 1.5 m -> verifier must reject
            ng_bad = tmp / "FO4SFNewGame_bad.esm"
            pb = wh.BINARY_ANCHORS["v111_pipboy_pickup"]["pos"]
            _write_synthetic_ref_esm(ng_bad, "CELL", [
                (b"REFR", 0x0300080F, (pb[0] + 1.5, pb[1], pb[2])),
                (b"REFR", 0x03000819, wh.BINARY_ANCHORS["v111_geardoor_console"]["pos"]),
            ])
            res_bad = wh.verify_against_staged_esms(newgame_esm=ng_bad)
            self.assertFalse(res_bad["pass"])
            self.assertTrue(any("v111_pipboy_pickup" in e for e in res_bad["issues"]))

    def test_exterior_commonwealth_navm_verifier_passes_and_catches_off_navmesh_segment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fo4_syn = Path(td) / "Fallout4_syn.esm"
            # Walkable corridor quad covering x in [-2470, -2450], y in [-1410, -1360]
            _write_synthetic_commonwealth_navm_esm(
                fo4_syn,
                (
                    (-2470.0, -1410.0, 125.0),
                    (-2450.0, -1410.0, 125.0),
                    (-2450.0, -1360.0, 120.0),
                    (-2470.0, -1360.0, 120.0),
                ),
            )
            on_seg = wh.WalkSegment(
                "L4", "4_on", "exterior_commonwealth", "On navmesh",
                (-2467.0, -1406.0, 125.0), (-2458.0, -1368.0, 121.0), 0.0, "ok", "surface_hilltop_arrival",
            )
            r_ok = wh.verify_exterior_navm_segments(fo4_syn, segments=(on_seg,), step_m=1.0)
            self.assertTrue(r_ok["pass"], r_ok["issues"])
            self.assertEqual(r_ok["hits"], r_ok["sampled_points"])

            # Off-navmesh segment exits east of x=-2450 -> MUST fail!
            off_seg = wh.WalkSegment(
                "L4", "4_off", "exterior_commonwealth", "Off navmesh",
                (-2467.0, -1406.0, 125.0), (-2405.0, -1402.0, 105.0), 0.0, "bad", "surface_hilltop_arrival",
            )
            r_bad = wh.verify_exterior_navm_segments(fo4_syn, segments=(off_seg,), step_m=1.0)
            self.assertFalse(r_bad["pass"])
            self.assertLess(r_bad["hits"], r_bad["sampled_points"])
            self.assertTrue(any("4_off" in e for e in r_bad["issues"]))

    def test_cli_subcommands_table_json_and_walk_markers_spec(self) -> None:
        p_json = subprocess.run([sys.executable, str(WALK_SCRIPT), "json"], capture_output=True, text=True, check=False)
        self.assertEqual(p_json.returncode, 0, p_json.stderr)
        data = json.loads(p_json.stdout)
        self.assertTrue(data["continuity"]["pass"])
        self.assertEqual(len(data["segments"]), 34)

        p_mk = subprocess.run([sys.executable, str(WALK_SCRIPT), "export-markers-json"], capture_output=True, text=True, check=False)
        self.assertEqual(p_mk.returncode, 0, p_mk.stderr)
        mk = json.loads(p_mk.stdout)
        self.assertEqual(mk["schema"], "fo4sf_walk_markers_v1")
        self.assertTrue(mk["optional_diagnostic_only"])
        self.assertEqual(mk["marker_count"], 34)

        p_tbl = subprocess.run([sys.executable, str(WALK_SCRIPT), "table"], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(p_tbl.returncode, 0, p_tbl.stderr)
        walk_doc = WALK_DOC.read_text(encoding="utf-8")
        self.assertIn("navmesh-verified offline; terrain on converted Commonwealth unproven in game", walk_doc)
        self.assertIn("in flight (`W1`)", walk_doc)
        # Ensure every single generated markdown table row appears verbatim in docs/testing/console-free-walk-list.md
        for line in p_tbl.stdout.splitlines():
            self.assertIn(line, walk_doc, f"Walk table row missing or drifted in console-free-walk-list.md: {line}")

    def test_r8_standin_truth_labels_across_all_five_quest_docs(self) -> None:
        a3 = QUEST_DOCS["a3"].read_text(encoding="utf-8")
        a4 = QUEST_DOCS["a4"].read_text(encoding="utf-8")
        a7 = QUEST_DOCS["a7"].read_text(encoding="utf-8")
        a7b = QUEST_DOCS["a7b"].read_text(encoding="utf-8")
        a7d = QUEST_DOCS["a7d"].read_text(encoding="utf-8")

        for name, txt in (("a3", a3), ("a4", a4), ("a7", a7), ("a7b", a7b), ("a7d", a7d)):
            self.assertIn("Truth Labels (`R8`", txt, f"{name} missing R8 Truth Labels section")
            self.assertIn("stand-in", txt.lower(), f"{name} must explicitly label stand-ins")

        # Specific R8 stand-ins required by Round 10 prompt & #402
        self.assertIn("0x000A15", a4)
        self.assertIn("WorkbenchBuildMsg", a4)
        self.assertIn("FO4SF_PrydwenArrived", a7b)
        self.assertIn("fallback=inline_scan", a7b)
        self.assertIn("0x00F2D3", a7b)
        self.assertIn("0x00F23D", a7b)
        self.assertIn("moves nobody", a7b.lower())
        self.assertIn("WorkbenchBuildMsg", a7d)
        self.assertIn("0x03D52E", a7d)
        self.assertIn("moves nobody", a7d.lower())

    def test_zero_drive_path_leaks_and_zero_forbidden_mod_names(self) -> None:
        files = [WALK_SCRIPT, WALK_DOC, HERE, *QUEST_DOCS.values()]
        for path in files:
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive path leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(txt), f"Forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
