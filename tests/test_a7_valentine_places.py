"""Unit tests for A7 next-two story missions & places (`Unlikely Valentine` MQ104 + `Getting a Clue` MQ105)."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts" / "terrain") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "terrain"))

import a7_valentine_places as a7  # noqa: E402

DOC_PATH = ROOT / "docs" / "quests" / "next-story-missions-a7.md"
SCRIPT_PATH = ROOT / "scripts" / "terrain" / "a7_valentine_places.py"
TEST_PATH = Path(__file__).resolve()


class TestA7ValentinePlaces(unittest.TestCase):
    def test_evaluate_a7_missions_passes_normal_and_open_mode(self) -> None:
        res = a7.evaluate_a7_missions()
        self.assertTrue(res["pass"])
        self.assertEqual(set(res["missions"].keys()), {"FO4SF_MQ104", "FO4SF_MQ105"})
        for qid, info in res["missions"].items():
            self.assertTrue(info["ok"], f"{qid} failed: {info}")
            self.assertTrue(info["normal"]["ok"], f"{qid} normal failed")
            self.assertEqual(info["normal"]["unreachable"], [])
            self.assertEqual(info["normal"]["stuck_stages"], [])
            self.assertTrue(info["open_mode"]["ok"], f"{qid} open_mode failed")
            self.assertEqual(info["open_mode"]["unreachable"], [])
            self.assertEqual(info["open_mode"]["stuck_stages"], [])
            self.assertTrue(info["w6_complete"])
            self.assertTrue(info["id_in_a7_and_a5"])
            self.assertEqual(info["known_bug_count"], 5)

    def test_single_edge_open_mode_mutation_mq104_stage_40(self) -> None:
        """Dropping ONLY the 40->60 open_mode_fallback on MQ104 must fail Open Mode while Normal passes."""
        mutated = copy.deepcopy(list(a7.A7_NEXT_MISSIONS))
        mq104 = mutated[0]
        self.assertEqual(mq104["quest_edid"], "FO4SF_MQ104")
        mq104["transitions"] = [
            t
            for t in mq104["transitions"]
            if not (t["from"] == 40 and t["to"] == 60 and not t["npc_gated"])
        ]
        res = a7.evaluate_a7_missions(mutated)
        self.assertFalse(res["pass"])
        m104 = res["missions"]["FO4SF_MQ104"]
        self.assertTrue(m104["normal"]["ok"])
        self.assertFalse(m104["open_mode"]["ok"])
        self.assertIn(40, m104["open_mode"]["stuck_stages"])
        self.assertFalse(m104["ok"])

    def test_single_edge_open_mode_mutation_mq105_stage_80(self) -> None:
        """Dropping ONLY the 80->100 open_mode_fallback on MQ105 must fail Open Mode while Normal passes."""
        mutated = copy.deepcopy(list(a7.A7_NEXT_MISSIONS))
        mq105 = mutated[1]
        self.assertEqual(mq105["quest_edid"], "FO4SF_MQ105")
        mq105["transitions"] = [
            t
            for t in mq105["transitions"]
            if not (t["from"] == 80 and t["to"] == 100 and not t["npc_gated"])
        ]
        res = a7.evaluate_a7_missions(mutated)
        self.assertFalse(res["pass"])
        m105 = res["missions"]["FO4SF_MQ105"]
        self.assertTrue(m105["normal"]["ok"])
        self.assertFalse(m105["open_mode"]["ok"])
        self.assertIn(80, m105["open_mode"]["stuck_stages"])
        self.assertFalse(m105["ok"])

    def test_single_edge_open_mode_mutation_mq105_stage_10(self) -> None:
        """Dropping ONLY the 10->30 open_mode_fallback on MQ105 must fail Open Mode while Normal passes."""
        mutated = copy.deepcopy(list(a7.A7_NEXT_MISSIONS))
        mq105 = mutated[1]
        mq105["transitions"] = [
            t
            for t in mq105["transitions"]
            if not (t["from"] == 10 and t["to"] == 30 and not t["npc_gated"])
        ]
        res = a7.evaluate_a7_missions(mutated)
        self.assertFalse(res["pass"])
        m105 = res["missions"]["FO4SF_MQ105"]
        self.assertTrue(m105["normal"]["ok"])
        self.assertFalse(m105["open_mode"]["ok"])
        self.assertIn(10, m105["open_mode"]["stuck_stages"])

    def test_normal_mode_stuck_stage_mutation(self) -> None:
        """Dropping all outgoing edges from stage 85 on MQ104 must fail Normal Mode."""
        mutated = copy.deepcopy(list(a7.A7_NEXT_MISSIONS))
        mq104 = mutated[0]
        mq104["transitions"] = [t for t in mq104["transitions"] if t["from"] != 85]
        res = a7.evaluate_a7_missions(mutated)
        self.assertFalse(res["pass"])
        m104 = res["missions"]["FO4SF_MQ104"]
        self.assertFalse(m104["normal"]["ok"])
        self.assertIn(85, m104["normal"]["stuck_stages"])

    def test_formid_reservations_disjoint_from_a4_and_inside_a5_scan_window(self) -> None:
        a4_lo, a4_hi = a7.A4_RESERVED_RANGE
        a7_lo, a7_hi = a7.A7_RESERVED_RANGE
        a5_lo, a5_hi = a7.A5_PIPBOY_SCAN_RANGE
        self.assertGreater(a7_lo, a4_hi)
        self.assertGreaterEqual(a7_lo, a5_lo)
        self.assertLessEqual(a7_hi, a5_hi)

        blocks = []
        for m in a7.A7_NEXT_MISSIONS:
            lid = int(m["reserved_local_id"])
            blo, bhi = m["reserved_block"]
            self.assertGreaterEqual(lid, blo)
            self.assertLessEqual(lid, bhi)
            self.assertGreaterEqual(blo, a7_lo)
            self.assertLessEqual(bhi, a7_hi)
            blocks.append((blo, bhi))

        blocks.sort()
        for (_, prev_hi), (next_lo, _) in zip(blocks, blocks[1:]):
            self.assertGreater(next_lo, prev_hi)

    def test_staged_places_cover_all_six_interiors_with_verified_port_ids(self) -> None:
        expected = {
            "FO4Port_Vault114": 0x01002593,
            "FO4Port_Vault11402": 0x010109FA,
            "FO4Port_DmndValentines01": 0x01006B30,
            "FO4Port_DmndStandsKellogg01": 0x0106B72C,
            "FO4Port_FortHagen01": 0x0100BA4B,
            "FO4Port_FortHagen02": 0x0100CFC6,
        }
        actual = {p.port_edid: p.port_cell_id for p in a7.A7_STAGED_PLACES}
        self.assertEqual(actual, expected)
        fo4_edids = {p.fo4_edid for p in a7.A7_STAGED_PLACES}
        self.assertIn("Vault114", fo4_edids)
        self.assertIn("DmndStandsKellogg01", fo4_edids)
        self.assertNotIn("ParkStreetStation01", fo4_edids)

    def test_pipboy_objective_tsv_rows_format_and_bounds(self) -> None:
        rows = a7.build_a7_pipboy_objective_rows()
        self.assertEqual(len(rows), 8)
        for row in rows:
            parts = row.split("\t")
            self.assertEqual(len(parts), 7, f"expected 7 TSV columns: {row}")
            plugin, local_hex, obj_num, x_s, y_s, loc, text = parts
            self.assertEqual(plugin, "FO4SFMission.esm")
            self.assertIn(local_hex, {"000A80", "000AB0"})
            self.assertGreater(int(obj_num), 0)
            x, y = float(x_s), float(y_s)
            self.assertTrue(a7.COMMONWEALTH_X_BOUNDS[0] <= x <= a7.COMMONWEALTH_X_BOUNDS[1])
            self.assertTrue(a7.COMMONWEALTH_Y_BOUNDS[0] <= y <= a7.COMMONWEALTH_Y_BOUNDS[1])
            self.assertTrue(loc.strip())
            self.assertTrue(text.strip())

        bad_x = copy.deepcopy(list(a7.A7_NEXT_MISSIONS[:1]))
        bad_x[0]["objectives"] = ((10, "Out of bounds", 999999.0, 0.0, "Nowhere"),)
        with self.assertRaises(ValueError):
            a7.build_a7_pipboy_objective_rows(bad_x)

        bad_nan = copy.deepcopy(list(a7.A7_NEXT_MISSIONS[:1]))
        bad_nan[0]["objectives"] = ((10, "NaN coord", float("nan"), 0.0, "Nowhere"),)
        with self.assertRaises(ValueError):
            a7.build_a7_pipboy_objective_rows(bad_nan)

    def test_cli_audit_and_emit_tsv(self) -> None:
        p1 = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "audit-a7"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p1.returncode, 0, p1.stderr)
        payload = json.loads(p1.stdout)
        self.assertTrue(payload["pass"])

        p2 = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "emit-tsv"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p2.returncode, 0, p2.stderr)
        lines = [ln for ln in p2.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 8)

    def test_doc_headers_bug_ledgers_p3_batch_ids_and_zero_drive_paths(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertTrue(lines, "A7 doc must not be empty")
        self.assertIn("Titles:", lines[0])
        self.assertIn("Modes:", lines[0])
        self.assertIn("Track:", lines[0])

        head10 = "\n".join(lines[:10]).lower()
        self.assertIn("prototype, offline", head10)
        self.assertIn("design only", head10)

        for code in [*(f"UVAL-0{i}" for i in range(1, 6)), *(f"CLUE-0{i}" for i in range(1, 6))]:
            self.assertIn(code, text)

        for batch_id in ("a7p1", "a7p2", "a7fh"):
            self.assertIn(f"bat {batch_id}", text)
            self.assertFalse(
                any(ch in batch_id.lower() for ch in ("m", "n", "v")),
                f"P3 batch ID {batch_id} must not contain M/N/V",
            )

        self.assertIn("## 6. Owner Questions", text)

        drive_pat = re.compile(r"\b[A-Za-z]:[\\/]")
        for path in (DOC_PATH, SCRIPT_PATH, TEST_PATH):
            raw = path.read_text(encoding="utf-8")
            self.assertIsNone(
                drive_pat.search(raw),
                f"Drive-letter path leak found in {path.name}",
            )


if __name__ == "__main__":
    unittest.main()
