"""Offline verification tests for A7b next-two story missions (`Reunions` MQ106 & `Dangerous Minds` MQ201/MQ202)."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
TERRAIN_DIR = REPO_ROOT / "scripts" / "terrain"
if str(TERRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(TERRAIN_DIR))

import a7b_reunions_places as a7b  # noqa: E402

A7B_DOC = REPO_ROOT / "docs" / "quests" / "next-story-missions-a7b.md"
A7B_SCRIPT = TERRAIN_DIR / "a7b_reunions_places.py"
DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = (
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
)


class A7bReunionsPlacesTests(unittest.TestCase):
    def test_formid_disjointness_and_next_a5_scan_range(self) -> None:
        res = a7b.check_formid_disjointness()
        self.assertTrue(res["pass"], res["issues"])
        self.assertEqual(res["a7b_range"], "0x000B00..0x000B7F")
        self.assertEqual(res["a5_next_scan_window"], "0x000800..0x000BFF")
        self.assertEqual(res["issues"], [])

    def test_all_six_interiors_b10_staged_cells_have_verified_port_ids(self) -> None:
        by_edid = {p.fo4_edid: p for p in a7b.A7B_STAGED_PLACES}
        expected = {
            "FortHagen01": 0x0100BA4B,
            "FortHagen02": 0x0100CFC6,
            "GoodneighborTheMemoryDen": 0x0100ED4A,
            "MQ203KelloggsBrain": 0x0100F23E,
            "PrydwenHull01": 0x01003846,
            "VirgilsLab01": 0x01069B10,
        }
        self.assertEqual(set(by_edid.keys()), set(expected.keys()))
        for edid, want_port_id in expected.items():
            self.assertEqual(by_edid[edid].port_cell_id, want_port_id, edid)
            self.assertGreater(by_edid[edid].staged_ref_count, 500, edid)

    def test_w6_normal_and_open_mode_pass_zero_unreachable_zero_stuck(self) -> None:
        res = a7b.evaluate_a7b_missions()
        self.assertTrue(res["pass"], res)
        self.assertEqual(len(res["missions"]), 2)
        for m in res["missions"]:
            self.assertTrue(m["pass"], m)
            self.assertEqual(m["normal"]["unreachable"], [])
            self.assertEqual(m["normal"]["stuck"], [])
            self.assertEqual(m["open_mode"]["unreachable"], [])
            self.assertEqual(m["open_mode"]["stuck"], [])

    def test_w6_mutation_removing_open_mode_edges_fails_open_mode_specifically(self) -> None:
        # Mutation 1: drop REUN-05 Open-Mode debrief bypass (200 -> 500) on MQ106
        m1 = copy.deepcopy(list(a7b.A7B_NEXT_MISSIONS))
        m1[0]["transitions"] = [
            tr for tr in m1[0]["transitions"]
            if not (tr["from"] == 200 and tr["to"] == 500 and not tr.get("npc_gated", False))
        ]
        r1 = a7b.evaluate_a7b_missions(m1)
        self.assertTrue(r1["missions"][0]["normal"]["pass"])
        self.assertFalse(r1["missions"][0]["open_mode"]["pass"])
        self.assertIn(200, r1["missions"][0]["open_mode"]["stuck"])

        # Mutation 2: drop MIND-01 Open-Mode Amari lab door bypass (10 -> 100) on MQ201
        m2 = copy.deepcopy(list(a7b.A7B_NEXT_MISSIONS))
        m2[1]["transitions"] = [
            tr for tr in m2[1]["transitions"]
            if not (tr["from"] == 10 and tr["to"] == 100 and not tr.get("npc_gated", False))
        ]
        r2 = a7b.evaluate_a7b_missions(m2)
        self.assertTrue(r2["missions"][1]["normal"]["pass"])
        self.assertFalse(r2["missions"][1]["open_mode"]["pass"])
        self.assertIn(10, r2["missions"][1]["open_mode"]["stuck"])

        # Mutation 3: drop MIND-05 Open-Mode Amari debrief bypass (120 -> 300) on MQ201
        m3 = copy.deepcopy(list(a7b.A7B_NEXT_MISSIONS))
        m3[1]["transitions"] = [
            tr for tr in m3[1]["transitions"]
            if not (tr["from"] == 120 and tr["to"] == 300 and not tr.get("npc_gated", False))
        ]
        r3 = a7b.evaluate_a7b_missions(m3)
        self.assertTrue(r3["missions"][1]["normal"]["pass"])
        self.assertFalse(r3["missions"][1]["open_mode"]["pass"])
        self.assertIn(120, r3["missions"][1]["open_mode"]["stuck"])

    def test_w6_mutation_normal_stuck_stage_is_caught(self) -> None:
        m = copy.deepcopy(list(a7b.A7B_NEXT_MISSIONS))
        m[0]["transitions"] = [tr for tr in m[0]["transitions"] if tr["from"] != 125]
        res = a7b.evaluate_a7b_missions(m)
        self.assertFalse(res["pass"])
        self.assertFalse(res["missions"][0]["normal"]["pass"])
        self.assertIn(125, res["missions"][0]["normal"]["stuck"])

    def test_a5_tsv_rows_valid_7_columns_within_commonwealth_bounds(self) -> None:
        rows = a7b.emit_a5_objective_tsv_rows()
        self.assertEqual(len(rows), 10)
        for row in rows:
            cols = row.split("\t")
            self.assertEqual(len(cols), 7, row)
            self.assertTrue(cols[0].startswith("0x000B"))
            int(cols[1])
            x, y = float(cols[4]), float(cols[5])
            self.assertGreaterEqual(x, a7b.COMMONWEALTH_X_BOUNDS[0])
            self.assertLessEqual(x, a7b.COMMONWEALTH_X_BOUNDS[1])
            self.assertGreaterEqual(y, a7b.COMMONWEALTH_Y_BOUNDS[0])
            self.assertLessEqual(y, a7b.COMMONWEALTH_Y_BOUNDS[1])

    def test_a5_tsv_rejects_nan_and_out_of_bounds_coordinates(self) -> None:
        bad_nan = copy.deepcopy(list(a7b.A7B_NEXT_MISSIONS))
        o0 = bad_nan[0]["objectives"][0]
        bad_nan[0]["objectives"] = ((o0[0], o0[1], float("nan"), o0[3], o0[4]),)
        with self.assertRaises(ValueError):
            a7b.emit_a5_objective_tsv_rows(bad_nan)

        bad_oob = copy.deepcopy(list(a7b.A7B_NEXT_MISSIONS))
        bad_oob[0]["objectives"] = ((o0[0], o0[1], 999999.0, o0[3], o0[4]),)
        with self.assertRaises(ValueError):
            a7b.emit_a5_objective_tsv_rows(bad_oob)

    def test_cli_subcommands_audit_a7b_and_emit_tsv(self) -> None:
        p1 = subprocess.run(
            [sys.executable, str(A7B_SCRIPT), "audit-a7b"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p1.returncode, 0, p1.stderr)
        data = json.loads(p1.stdout)
        self.assertTrue(data["pass"])
        self.assertEqual(len(data["staged_places"]), 6)

        p2 = subprocess.run(
            [sys.executable, str(A7B_SCRIPT), "emit-tsv"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p2.returncode, 0, p2.stderr)
        lines = [ln for ln in p2.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 10)

    def test_p3_safe_batch_names_have_zero_m_n_v(self) -> None:
        bat_ids = []
        for m in a7b.A7B_NEXT_MISSIONS:
            for b in m["break_it_batches"]:
                bat_ids.append(b["bat_id"])
                cmd = f"bat {b['bat_id']}"
                for bad in ("m", "n", "v"):
                    self.assertNotIn(bad, cmd.lower(), f"P3 violation in {cmd}")
        self.assertEqual(bat_ids, ["a7b1", "a7b2", "a7b3", "a7b4"])

    def test_doc_headers_ledgers_owner_questions_and_zero_drive_or_mod_leaks(self) -> None:
        doc_txt = A7B_DOC.read_text(encoding="utf-8")
        lines = doc_txt.splitlines()
        self.assertIn("Titles: Fallout 4 -> all 7 Fallout titles", lines[0])
        self.assertIn("Modes: Story & Warfare", lines[0])
        self.assertIn("Track: Track 1", lines[0])
        top_lines = "\n".join(lines[:8]).lower()
        self.assertIn("prototype, offline", top_lines)
        self.assertIn("design only", top_lines)
        self.assertIn("whole-scope", top_lines)
        self.assertIn("## 6. Consolidated Owner Questions", doc_txt)
        for bug_id in (
            "REUN-01", "REUN-02", "REUN-03", "REUN-04", "REUN-05",
            "MIND-01", "MIND-02", "MIND-03", "MIND-04", "MIND-05",
        ):
            self.assertIn(bug_id, doc_txt)
        for path in (A7B_DOC, A7B_SCRIPT, HERE):
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"drive path leak in {path.name}")
            for pat in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(pat.search(txt), f"forbidden mod name in {path.name}")


if __name__ == "__main__":
    unittest.main()
